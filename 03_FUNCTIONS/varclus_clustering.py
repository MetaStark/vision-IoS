#!/usr/bin/env python3
"""
VARCLUS VARIABLE CLUSTERING (STIG-2025-001 Compliant)
=====================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - Hierarchical Causal Discovery
Classification: Tier-1 Cognitive Infrastructure

Purpose:
    Reduce O(N³) PCMCI complexity by clustering 500 assets into ~30 macro clusters.
    Enables tractable causal discovery on cluster centroids.

Key Insight:
    PCMCI on 500 assets = months of compute
    VarClus → 30 clusters → PCMCI on centroids = hours

CRITICAL: Clustering on RETURNS (stationary), NOT raw prices (non-stationary)

Usage:
    from varclus_clustering import VarClusEngine

    engine = VarClusEngine()
    clusters = engine.cluster_assets(assets, n_clusters=30)
    centroids = engine.get_cluster_centroids()
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from dotenv import load_dotenv

# Clustering imports
try:
    from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
    from scipy.spatial.distance import squareform
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("WARNING: scipy/sklearn not available. Using simplified clustering.")

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


@dataclass
class AssetFeatures:
    """Stationary features for clustering"""
    asset: str
    returns: np.ndarray           # Log returns
    volatility: np.ndarray        # Rolling volatility
    volume_z: np.ndarray          # Z-scored volume
    momentum: np.ndarray          # Momentum indicator


@dataclass
class ClusterInfo:
    """Cluster metadata"""
    cluster_id: int
    name: str                     # e.g., "Tech", "Energy", "Defensive"
    members: List[str]
    centroid: np.ndarray
    intra_correlation: float      # Average correlation within cluster
    representative_asset: str     # Most central asset
    sector_composition: Dict[str, int]


@dataclass
class ClusteringResult:
    """Full clustering result"""
    n_clusters: int
    n_assets: int
    clusters: Dict[int, ClusterInfo]
    asset_to_cluster: Dict[str, int]
    silhouette_score: float
    created_at: datetime


class VarClusEngine:
    """
    Variable Clustering Engine (STIG-2025-001)

    Implements hierarchical clustering on asset return covariance structure
    to reduce dimensionality for causal discovery.

    Algorithm:
    1. Extract stationary features (returns, vol, volume_z)
    2. Build correlation matrix
    3. Ward hierarchical clustering
    4. Cut dendrogram at n_clusters
    5. Compute cluster centroids
    """

    DEFAULT_CLUSTERS = 30
    MIN_HISTORY_DAYS = 252        # 1 year minimum for clustering
    LOOKBACK_DAYS = 756           # 3 years for robust clustering

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self._features_cache: Dict[str, AssetFeatures] = {}
        self._clustering_result: Optional[ClusteringResult] = None

    def _get_price_data(self, asset: str, days: int = 756) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Fetch price and volume data"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT timestamp::date as date, close, volume
                FROM fhq_market.prices
                WHERE canonical_id = %s
                  AND timestamp >= NOW() - INTERVAL '%s days'
                ORDER BY timestamp ASC
            """, (asset, days + 30))
            rows = cur.fetchall()

        if len(rows) < self.MIN_HISTORY_DAYS:
            return np.array([]), np.array([]), np.array([])

        dates = [r['date'] for r in rows]
        closes = np.array([float(r['close']) for r in rows])
        volumes = np.array([float(r['volume']) if r['volume'] else 0 for r in rows])

        return closes, volumes, dates

    def extract_features(self, asset: str) -> Optional[AssetFeatures]:
        """
        Extract stationary features for clustering.

        CRITICAL: Use returns, NOT raw prices (non-stationary)
        """
        if asset in self._features_cache:
            return self._features_cache[asset]

        closes, volumes, dates = self._get_price_data(asset, self.LOOKBACK_DAYS)

        if len(closes) < self.MIN_HISTORY_DAYS:
            return None

        # Log returns (stationary)
        returns = np.diff(np.log(closes))

        # Rolling volatility (20-day)
        volatility = np.array([
            np.std(returns[max(0, i-20):i]) if i >= 20 else np.std(returns[:i+1])
            for i in range(len(returns))
        ])

        # Z-scored volume
        volume_mean = np.mean(volumes[1:])
        volume_std = np.std(volumes[1:])
        volume_z = (volumes[1:] - volume_mean) / volume_std if volume_std > 0 else np.zeros(len(volumes)-1)

        # Momentum (20-day return)
        momentum = np.array([
            returns[max(0, i-20):i].sum() if i >= 20 else returns[:i+1].sum()
            for i in range(len(returns))
        ])

        features = AssetFeatures(
            asset=asset,
            returns=returns,
            volatility=volatility,
            volume_z=volume_z,
            momentum=momentum
        )

        self._features_cache[asset] = features
        return features

    def _build_correlation_matrix(self, assets: List[str]) -> Tuple[np.ndarray, List[str]]:
        """Build return correlation matrix for clustering"""
        # Extract features for all assets
        valid_assets = []
        returns_matrix = []

        for asset in assets:
            features = self.extract_features(asset)
            if features is not None and len(features.returns) >= self.MIN_HISTORY_DAYS:
                valid_assets.append(asset)
                returns_matrix.append(features.returns[-self.MIN_HISTORY_DAYS:])

        if len(valid_assets) < 2:
            return np.array([]), []

        # Align lengths
        min_len = min(len(r) for r in returns_matrix)
        returns_matrix = np.array([r[-min_len:] for r in returns_matrix])

        # Compute correlation matrix
        corr_matrix = np.corrcoef(returns_matrix)

        # Handle NaN
        corr_matrix = np.nan_to_num(corr_matrix, nan=0)

        return corr_matrix, valid_assets

    def cluster_assets(
        self,
        assets: List[str],
        n_clusters: int = None,
        method: str = 'ward'
    ) -> ClusteringResult:
        """
        Cluster assets using hierarchical clustering on return correlations.

        Args:
            assets: List of asset identifiers
            n_clusters: Target number of clusters (default 30)
            method: Linkage method ('ward', 'complete', 'average')

        Returns:
            ClusteringResult with cluster assignments and metadata
        """
        n_clusters = n_clusters or self.DEFAULT_CLUSTERS

        print(f"[VARCLUS] Clustering {len(assets)} assets into {n_clusters} clusters...")

        # Build correlation matrix
        corr_matrix, valid_assets = self._build_correlation_matrix(assets)

        if len(valid_assets) < n_clusters:
            print(f"[VARCLUS] Only {len(valid_assets)} valid assets, reducing clusters")
            n_clusters = max(2, len(valid_assets) // 3)

        if len(valid_assets) < 2:
            return self._empty_result()

        # Convert correlation to distance
        # distance = 1 - |correlation|
        dist_matrix = 1 - np.abs(corr_matrix)
        np.fill_diagonal(dist_matrix, 0)

        # Force symmetry (handle floating point precision)
        dist_matrix = (dist_matrix + dist_matrix.T) / 2

        if SCIPY_AVAILABLE:
            # Hierarchical clustering
            condensed_dist = squareform(dist_matrix)
            Z = linkage(condensed_dist, method=method)

            # Cut dendrogram
            cluster_labels = fcluster(Z, t=n_clusters, criterion='maxclust')
        else:
            # Simplified clustering without scipy
            cluster_labels = self._simple_clustering(corr_matrix, n_clusters)

        # Build cluster info
        clusters = {}
        asset_to_cluster = {}

        for i, asset in enumerate(valid_assets):
            cluster_id = int(cluster_labels[i])
            asset_to_cluster[asset] = cluster_id

            if cluster_id not in clusters:
                clusters[cluster_id] = {
                    'members': [],
                    'returns': []
                }
            clusters[cluster_id]['members'].append(asset)

            features = self._features_cache.get(asset)
            if features:
                clusters[cluster_id]['returns'].append(features.returns[-self.MIN_HISTORY_DAYS:])

        # Compute cluster metadata
        cluster_infos = {}
        for cluster_id, data in clusters.items():
            members = data['members']
            returns_list = data['returns']

            # Centroid (average returns)
            if returns_list:
                min_len = min(len(r) for r in returns_list)
                aligned = np.array([r[-min_len:] for r in returns_list])
                centroid = np.mean(aligned, axis=0)
            else:
                centroid = np.array([])

            # Intra-cluster correlation
            if len(returns_list) > 1:
                intra_corr = np.mean([
                    np.corrcoef(returns_list[i][-min_len:], returns_list[j][-min_len:])[0, 1]
                    for i in range(len(returns_list))
                    for j in range(i+1, len(returns_list))
                ])
            else:
                intra_corr = 1.0

            # Representative asset (most correlated with centroid)
            rep_asset = members[0]
            if len(members) > 1 and len(centroid) > 0:
                best_corr = -1
                for m in members:
                    feat = self._features_cache.get(m)
                    if feat and len(feat.returns) >= len(centroid):
                        corr = np.corrcoef(feat.returns[-len(centroid):], centroid)[0, 1]
                        if corr > best_corr:
                            best_corr = corr
                            rep_asset = m

            cluster_infos[cluster_id] = ClusterInfo(
                cluster_id=cluster_id,
                name=f"Cluster_{cluster_id}",
                members=members,
                centroid=centroid,
                intra_correlation=round(float(np.nan_to_num(intra_corr, nan=0)), 4),
                representative_asset=rep_asset,
                sector_composition={}
            )

        # Calculate silhouette score (simplified)
        silhouette = self._calculate_silhouette(corr_matrix, cluster_labels)

        result = ClusteringResult(
            n_clusters=len(cluster_infos),
            n_assets=len(valid_assets),
            clusters=cluster_infos,
            asset_to_cluster=asset_to_cluster,
            silhouette_score=round(silhouette, 4),
            created_at=datetime.now(timezone.utc)
        )

        self._clustering_result = result
        self._log_clustering(result)

        print(f"[VARCLUS] Created {len(cluster_infos)} clusters with silhouette={silhouette:.4f}")

        return result

    def _simple_clustering(self, corr_matrix: np.ndarray, n_clusters: int) -> np.ndarray:
        """Simple clustering without scipy"""
        n = len(corr_matrix)
        labels = np.zeros(n, dtype=int)

        # Greedy assignment based on correlation
        assigned = set()
        cluster_id = 1

        for i in range(n):
            if i in assigned:
                continue

            labels[i] = cluster_id
            assigned.add(i)

            # Find similar assets
            for j in range(i+1, n):
                if j not in assigned and corr_matrix[i, j] > 0.5:
                    labels[j] = cluster_id
                    assigned.add(j)

                    if len([x for x in labels if x == cluster_id]) >= n // n_clusters:
                        break

            cluster_id += 1
            if cluster_id > n_clusters:
                cluster_id = 1

        return labels

    def _calculate_silhouette(self, corr_matrix: np.ndarray, labels: np.ndarray) -> float:
        """Calculate simplified silhouette score"""
        n = len(labels)
        if n < 2:
            return 0.0

        silhouettes = []
        for i in range(n):
            # a(i) = average distance to same cluster
            same_cluster = [j for j in range(n) if labels[j] == labels[i] and j != i]
            if same_cluster:
                a_i = np.mean([1 - corr_matrix[i, j] for j in same_cluster])
            else:
                a_i = 0

            # b(i) = min average distance to other clusters
            other_clusters = set(labels) - {labels[i]}
            b_i = float('inf')
            for c in other_clusters:
                other_members = [j for j in range(n) if labels[j] == c]
                if other_members:
                    avg_dist = np.mean([1 - corr_matrix[i, j] for j in other_members])
                    b_i = min(b_i, avg_dist)

            if b_i == float('inf'):
                b_i = a_i

            if max(a_i, b_i) > 0:
                silhouettes.append((b_i - a_i) / max(a_i, b_i))

        return np.mean(silhouettes) if silhouettes else 0.0

    def _empty_result(self) -> ClusteringResult:
        return ClusteringResult(
            n_clusters=0,
            n_assets=0,
            clusters={},
            asset_to_cluster={},
            silhouette_score=0,
            created_at=datetime.now(timezone.utc)
        )

    def get_cluster_centroids(self) -> Dict[int, np.ndarray]:
        """Get centroids for all clusters"""
        if not self._clustering_result:
            return {}

        return {
            cid: info.centroid
            for cid, info in self._clustering_result.clusters.items()
        }

    def get_cluster_members(self, cluster_id: int) -> List[str]:
        """Get members of a specific cluster"""
        if not self._clustering_result:
            return []

        cluster = self._clustering_result.clusters.get(cluster_id)
        return cluster.members if cluster else []

    def get_asset_cluster(self, asset: str) -> Optional[int]:
        """Get cluster ID for an asset"""
        if not self._clustering_result:
            return None
        return self._clustering_result.asset_to_cluster.get(asset)

    def _log_clustering(self, result: ClusteringResult):
        """Log clustering result to database"""
        try:
            with self.conn.cursor() as cur:
                # Log each cluster
                for cluster_id, info in result.clusters.items():
                    cur.execute("""
                        INSERT INTO fhq_cognition.asset_clusters
                        (cluster_id, cluster_name, members, representative_asset,
                         intra_correlation, member_count, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (cluster_id) DO UPDATE SET
                            members = EXCLUDED.members,
                            intra_correlation = EXCLUDED.intra_correlation,
                            created_at = EXCLUDED.created_at
                    """, (
                        cluster_id,
                        info.name,
                        json.dumps(info.members),
                        info.representative_asset,
                        info.intra_correlation,
                        len(info.members),
                        result.created_at
                    ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass


if __name__ == "__main__":
    print("=" * 60)
    print("VARCLUS VARIABLE CLUSTERING - SELF TEST")
    print("=" * 60)

    engine = VarClusEngine()

    # Get all assets
    print("\n[1] Fetching assets...")
    with engine.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE timestamp >= NOW() - INTERVAL '300 days'
            GROUP BY canonical_id
            HAVING COUNT(*) >= 200
            ORDER BY canonical_id
        """)
        assets = [r['canonical_id'] for r in cur.fetchall()]

    print(f"   Found {len(assets)} assets with sufficient history")

    if len(assets) >= 10:
        # Cluster into reasonable number based on asset count
        n_clusters = min(10, len(assets) // 3)

        print(f"\n[2] Clustering into {n_clusters} clusters...")
        result = engine.cluster_assets(assets, n_clusters=n_clusters)

        print(f"\n[3] Clustering Results:")
        print(f"   Assets: {result.n_assets}")
        print(f"   Clusters: {result.n_clusters}")
        print(f"   Silhouette: {result.silhouette_score}")

        print(f"\n[4] Cluster Details:")
        for cid, info in sorted(result.clusters.items()):
            print(f"\n   Cluster {cid}: {len(info.members)} members")
            print(f"      Representative: {info.representative_asset}")
            print(f"      Intra-corr: {info.intra_correlation:.4f}")
            print(f"      Members: {info.members[:5]}{'...' if len(info.members) > 5 else ''}")

        # Show centroid stats
        print(f"\n[5] Centroid Statistics:")
        centroids = engine.get_cluster_centroids()
        for cid, centroid in centroids.items():
            if len(centroid) > 0:
                print(f"   Cluster {cid}: len={len(centroid)}, mean={np.mean(centroid):.6f}, std={np.std(centroid):.6f}")
    else:
        print("   Insufficient assets for clustering test")

    print("\n" + "=" * 60)
    print("VARCLUS VARIABLE CLUSTERING - TEST COMPLETE")
    print("=" * 60)
