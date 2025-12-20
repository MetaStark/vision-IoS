#!/usr/bin/env python3
"""
IoS-019 CLUSTER CAUSAL ENGINE (STIG-2025-001 Compliant)
=======================================================
Authority: STIG (CTO)
ADR Reference: STIG-2025-001 Directive - Hierarchical Causal Discovery
Classification: Tier-1 Cognitive Infrastructure

Purpose:
    Discover causal relationships between asset clusters using PCMCI.
    Enables "lead-lag" alpha by identifying causal parents.

Architecture:
    500 Assets → VarClus → 30 Clusters → PCMCI on Centroids → Causal Graph

Key Insight:
    If Oil cluster leads Energy cluster causally,
    individual oil stocks can predict energy stock moves.

Usage:
    from ios019_cluster_causal_engine import ClusterCausalEngine

    engine = ClusterCausalEngine()
    graph = engine.discover_macro_causality()
    parents = engine.get_causal_parents('AAPL')
"""

import os
import json
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from dotenv import load_dotenv

# Import clustering
try:
    from varclus_clustering import VarClusEngine, ClusteringResult
    VARCLUS_AVAILABLE = True
except ImportError:
    VARCLUS_AVAILABLE = False

# PCMCI imports
try:
    from tigramite import data_processing as pp
    from tigramite.pcmci import PCMCI
    from tigramite.independence_tests import ParCorr
    PCMCI_AVAILABLE = True
except ImportError:
    PCMCI_AVAILABLE = False
    print("WARNING: tigramite not available. Using simplified causal discovery.")

load_dotenv()

DB_CONFIG = {
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': int(os.getenv('PGPORT', '54322')),
    'database': os.getenv('PGDATABASE', 'postgres'),
    'user': os.getenv('PGUSER', 'postgres'),
    'password': os.getenv('PGPASSWORD', 'postgres')
}


@dataclass
class CausalEdge:
    """Causal relationship between two entities"""
    source: str                   # Parent (cause)
    target: str                   # Child (effect)
    lag: int                      # Time lag in periods
    strength: float               # Edge strength (-1 to 1)
    p_value: float                # Statistical significance
    edge_type: str                # 'macro' (cluster) or 'micro' (asset)
    discovered_at: datetime


@dataclass
class CausalGraph:
    """Complete causal graph"""
    nodes: List[str]
    edges: List[CausalEdge]
    adjacency: Dict[str, List[str]]  # node -> list of children
    parents: Dict[str, List[str]]    # node -> list of parents
    graph_type: str                  # 'macro' or 'micro'
    created_at: datetime


class ClusterCausalEngine:
    """
    Cluster Causal Discovery Engine (STIG-2025-001)

    Implements hierarchical causal discovery:
    1. Macro-level: PCMCI on cluster centroids (cheap!)
    2. Micro-level: PCMCI within linked clusters (targeted)

    This solves the O(N³) complexity problem by divide-and-conquer.
    """

    # PCMCI Parameters
    TAU_MAX = 5                   # Maximum time lag
    PC_ALPHA = 0.05               # Significance level
    MIN_EDGE_STRENGTH = 0.1       # Minimum |strength| to keep edge

    def __init__(self):
        self.conn = psycopg2.connect(**DB_CONFIG)
        self.varclus = VarClusEngine() if VARCLUS_AVAILABLE else None
        self._clustering_result: Optional[ClusteringResult] = None
        self._macro_graph: Optional[CausalGraph] = None
        self._micro_graphs: Dict[str, CausalGraph] = {}

    def _prepare_dataframe(self, data: Dict[str, np.ndarray]) -> Tuple:
        """Prepare data for PCMCI"""
        # Align all series
        min_len = min(len(v) for v in data.values())
        var_names = list(data.keys())

        # Stack into array (T x N)
        aligned = np.column_stack([data[v][-min_len:] for v in var_names])

        if PCMCI_AVAILABLE:
            dataframe = pp.DataFrame(aligned, var_names=var_names)
            return dataframe, var_names
        else:
            return aligned, var_names

    def _run_pcmci(self, data: Dict[str, np.ndarray]) -> List[CausalEdge]:
        """
        Run PCMCI causal discovery on data.

        Returns list of significant causal edges.
        """
        if len(data) < 2:
            return []

        edges = []
        var_names = list(data.keys())

        if PCMCI_AVAILABLE:
            dataframe, var_names = self._prepare_dataframe(data)

            # Run PCMCI
            parcorr = ParCorr(significance='analytic')
            pcmci = PCMCI(dataframe=dataframe, cond_ind_test=parcorr)

            results = pcmci.run_pcmci(
                tau_max=self.TAU_MAX,
                pc_alpha=self.PC_ALPHA
            )

            # Extract significant edges
            p_matrix = results['p_matrix']
            val_matrix = results['val_matrix']

            for i, source in enumerate(var_names):
                for j, target in enumerate(var_names):
                    if i == j:
                        continue

                    for lag in range(1, self.TAU_MAX + 1):
                        p_val = p_matrix[i, j, lag]
                        strength = val_matrix[i, j, lag]

                        if p_val < self.PC_ALPHA and abs(strength) > self.MIN_EDGE_STRENGTH:
                            edges.append(CausalEdge(
                                source=source,
                                target=target,
                                lag=lag,
                                strength=round(float(strength), 4),
                                p_value=round(float(p_val), 4),
                                edge_type='discovered',
                                discovered_at=datetime.now(timezone.utc)
                            ))
        else:
            # Simplified causal discovery using Granger-like approach
            edges = self._simple_causal_discovery(data, var_names)

        return edges

    def _simple_causal_discovery(self, data: Dict[str, np.ndarray], var_names: List[str]) -> List[CausalEdge]:
        """Simplified causal discovery without PCMCI"""
        edges = []
        min_len = min(len(v) for v in data.values())

        for i, source in enumerate(var_names):
            for j, target in enumerate(var_names):
                if i == j:
                    continue

                source_data = data[source][-min_len:]
                target_data = data[target][-min_len:]

                # Test lagged correlation as proxy for causality
                for lag in range(1, self.TAU_MAX + 1):
                    if lag >= min_len:
                        continue

                    # Correlation of source[t-lag] with target[t]
                    lagged_source = source_data[:-lag]
                    current_target = target_data[lag:]

                    if len(lagged_source) < 20:
                        continue

                    corr = np.corrcoef(lagged_source, current_target)[0, 1]

                    # Simple significance test
                    n = len(lagged_source)
                    t_stat = corr * np.sqrt(n - 2) / np.sqrt(1 - corr**2) if abs(corr) < 1 else 0
                    p_val = 2 * (1 - min(0.999, abs(t_stat) / 10))  # Rough approximation

                    if abs(corr) > self.MIN_EDGE_STRENGTH and p_val < self.PC_ALPHA:
                        edges.append(CausalEdge(
                            source=source,
                            target=target,
                            lag=lag,
                            strength=round(float(corr), 4),
                            p_value=round(float(p_val), 4),
                            edge_type='lagged_corr',
                            discovered_at=datetime.now(timezone.utc)
                        ))

        return edges

    def discover_macro_causality(self, assets: List[str] = None, n_clusters: int = 30) -> CausalGraph:
        """
        Discover causal relationships at cluster level.

        This is the CHEAP step - PCMCI on ~30 cluster centroids.
        """
        print(f"[CAUSAL] Starting macro causal discovery...")

        # Get or create clustering
        if assets and self.varclus:
            self._clustering_result = self.varclus.cluster_assets(assets, n_clusters)
        elif not self._clustering_result:
            # Load from database
            self._clustering_result = self._load_clustering()

        if not self._clustering_result or not self._clustering_result.clusters:
            print("[CAUSAL] No clustering available")
            return self._empty_graph('macro')

        # Get cluster centroids
        centroids = {}
        for cid, info in self._clustering_result.clusters.items():
            if len(info.centroid) > 0:
                centroids[f"Cluster_{cid}"] = info.centroid

        if len(centroids) < 2:
            return self._empty_graph('macro')

        print(f"[CAUSAL] Running PCMCI on {len(centroids)} cluster centroids...")

        # Run PCMCI on centroids
        edges = self._run_pcmci(centroids)

        # Build graph
        nodes = list(centroids.keys())
        adjacency = defaultdict(list)
        parents = defaultdict(list)

        for edge in edges:
            adjacency[edge.source].append(edge.target)
            parents[edge.target].append(edge.source)

        graph = CausalGraph(
            nodes=nodes,
            edges=edges,
            adjacency=dict(adjacency),
            parents=dict(parents),
            graph_type='macro',
            created_at=datetime.now(timezone.utc)
        )

        self._macro_graph = graph
        self._log_graph(graph)

        print(f"[CAUSAL] Discovered {len(edges)} macro causal edges")

        return graph

    def discover_micro_causality(self, cluster_a: int, cluster_b: int) -> CausalGraph:
        """
        Discover causal relationships between assets in two linked clusters.

        This is the TARGETED step - only run when macro-link exists.
        """
        if not self._clustering_result:
            return self._empty_graph('micro')

        cluster_a_info = self._clustering_result.clusters.get(cluster_a)
        cluster_b_info = self._clustering_result.clusters.get(cluster_b)

        if not cluster_a_info or not cluster_b_info:
            return self._empty_graph('micro')

        # Get asset returns for both clusters
        assets_data = {}

        for asset in cluster_a_info.members + cluster_b_info.members:
            if self.varclus and asset in self.varclus._features_cache:
                features = self.varclus._features_cache[asset]
                assets_data[asset] = features.returns

        if len(assets_data) < 2:
            return self._empty_graph('micro')

        print(f"[CAUSAL] Running micro PCMCI on {len(assets_data)} assets from clusters {cluster_a}, {cluster_b}")

        # Run PCMCI
        edges = self._run_pcmci(assets_data)

        # Mark edges as micro
        for edge in edges:
            edge.edge_type = 'micro'

        # Build graph
        nodes = list(assets_data.keys())
        adjacency = defaultdict(list)
        parents = defaultdict(list)

        for edge in edges:
            adjacency[edge.source].append(edge.target)
            parents[edge.target].append(edge.source)

        graph = CausalGraph(
            nodes=nodes,
            edges=edges,
            adjacency=dict(adjacency),
            parents=dict(parents),
            graph_type='micro',
            created_at=datetime.now(timezone.utc)
        )

        key = f"{cluster_a}_{cluster_b}"
        self._micro_graphs[key] = graph
        self._log_graph(graph)

        return graph

    def get_causal_parents(self, asset: str) -> List[Tuple[str, float, int]]:
        """
        Get causal parents for an asset.

        Returns list of (parent_asset, strength, lag)
        """
        parents = []

        # Check micro graphs
        for key, graph in self._micro_graphs.items():
            for edge in graph.edges:
                if edge.target == asset:
                    parents.append((edge.source, edge.strength, edge.lag))

        # If no micro parents, use macro (cluster) parents
        if not parents and self._macro_graph and self._clustering_result:
            asset_cluster = self._clustering_result.asset_to_cluster.get(asset)
            if asset_cluster:
                cluster_name = f"Cluster_{asset_cluster}"
                cluster_parents = self._macro_graph.parents.get(cluster_name, [])

                for parent_cluster in cluster_parents:
                    # Get representative asset from parent cluster
                    parent_id = int(parent_cluster.split('_')[1])
                    parent_info = self._clustering_result.clusters.get(parent_id)
                    if parent_info:
                        # Find edge strength
                        for edge in self._macro_graph.edges:
                            if edge.source == parent_cluster and edge.target == cluster_name:
                                parents.append((
                                    parent_info.representative_asset,
                                    edge.strength,
                                    edge.lag
                                ))
                                break

        return parents

    def get_causal_children(self, asset: str) -> List[Tuple[str, float, int]]:
        """Get causal children (assets that this asset predicts)"""
        children = []

        for key, graph in self._micro_graphs.items():
            for edge in graph.edges:
                if edge.source == asset:
                    children.append((edge.target, edge.strength, edge.lag))

        return children

    def _empty_graph(self, graph_type: str) -> CausalGraph:
        return CausalGraph(
            nodes=[],
            edges=[],
            adjacency={},
            parents={},
            graph_type=graph_type,
            created_at=datetime.now(timezone.utc)
        )

    def _load_clustering(self) -> Optional[ClusteringResult]:
        """Load clustering from database"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT cluster_id, cluster_name, members, representative_asset,
                           intra_correlation
                    FROM fhq_cognition.asset_clusters
                    ORDER BY cluster_id
                """)
                rows = cur.fetchall()

            if not rows:
                return None

            from varclus_clustering import ClusterInfo, ClusteringResult

            clusters = {}
            asset_to_cluster = {}

            for row in rows:
                members = json.loads(row['members']) if isinstance(row['members'], str) else row['members']
                cluster_id = row['cluster_id']

                clusters[cluster_id] = ClusterInfo(
                    cluster_id=cluster_id,
                    name=row['cluster_name'],
                    members=members,
                    centroid=np.array([]),  # Would need to recompute
                    intra_correlation=row['intra_correlation'],
                    representative_asset=row['representative_asset'],
                    sector_composition={}
                )

                for asset in members:
                    asset_to_cluster[asset] = cluster_id

            return ClusteringResult(
                n_clusters=len(clusters),
                n_assets=len(asset_to_cluster),
                clusters=clusters,
                asset_to_cluster=asset_to_cluster,
                silhouette_score=0,
                created_at=datetime.now(timezone.utc)
            )
        except Exception:
            return None

    def _log_graph(self, graph: CausalGraph):
        """Log causal graph to database"""
        try:
            with self.conn.cursor() as cur:
                for edge in graph.edges:
                    cur.execute("""
                        INSERT INTO fhq_cognition.causal_edges
                        (source_node, target_node, lag, strength, p_value,
                         edge_type, discovered_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        edge.source,
                        edge.target,
                        edge.lag,
                        edge.strength,
                        edge.p_value,
                        edge.edge_type,
                        edge.discovered_at
                    ))
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            pass


if __name__ == "__main__":
    print("=" * 60)
    print("IoS-019 CLUSTER CAUSAL ENGINE - SELF TEST")
    print("=" * 60)

    engine = ClusterCausalEngine()

    # Get assets
    print("\n[1] Fetching assets...")
    with engine.conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT DISTINCT canonical_id
            FROM fhq_market.prices
            WHERE timestamp >= NOW() - INTERVAL '300 days'
            GROUP BY canonical_id
            HAVING COUNT(*) >= 200
            ORDER BY canonical_id
            LIMIT 50
        """)
        assets = [r['canonical_id'] for r in cur.fetchall()]

    print(f"   Found {len(assets)} assets")

    if len(assets) >= 10:
        # Discover macro causality
        print(f"\n[2] Discovering macro causality...")
        n_clusters = min(8, len(assets) // 4)
        macro_graph = engine.discover_macro_causality(assets, n_clusters=n_clusters)

        print(f"\n[3] Macro Causal Graph:")
        print(f"   Nodes: {len(macro_graph.nodes)}")
        print(f"   Edges: {len(macro_graph.edges)}")

        if macro_graph.edges:
            print(f"\n   Top Causal Edges:")
            sorted_edges = sorted(macro_graph.edges, key=lambda e: abs(e.strength), reverse=True)
            for edge in sorted_edges[:5]:
                print(f"   {edge.source} -> {edge.target} (lag={edge.lag}, str={edge.strength:.3f})")

        # Test causal parents lookup
        if assets:
            print(f"\n[4] Causal Parents for {assets[0]}:")
            parents = engine.get_causal_parents(assets[0])
            if parents:
                for parent, strength, lag in parents:
                    print(f"   <- {parent} (str={strength:.3f}, lag={lag})")
            else:
                print("   No direct causal parents found")

        # If macro edges exist, do micro discovery
        if macro_graph.edges:
            edge = macro_graph.edges[0]
            source_id = int(edge.source.split('_')[1])
            target_id = int(edge.target.split('_')[1])

            print(f"\n[5] Discovering micro causality between clusters {source_id} and {target_id}...")
            micro_graph = engine.discover_micro_causality(source_id, target_id)

            print(f"   Micro edges: {len(micro_graph.edges)}")
            for edge in micro_graph.edges[:3]:
                print(f"   {edge.source} -> {edge.target} (lag={edge.lag})")
    else:
        print("   Insufficient assets for causal discovery")

    print("\n" + "=" * 60)
    print("IoS-019 CLUSTER CAUSAL ENGINE - TEST COMPLETE")
    print("=" * 60)
