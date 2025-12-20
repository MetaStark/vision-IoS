#!/usr/bin/env python3
"""
IoS-003 v4 Input-Output HMM with Online EM

Implements modernized HMM regime detection:
- Student-t emissions for fat tails
- IOHMM with covariate-driven transition probabilities
- Online EM for continuous parameter updates
- Bayesian Online Changepoint Detection (BOCD)

Authority: CEO Directive IoS-003 v4
Date: 2025-12-11
Executor: STIG (CTO)

References:
- IOHMM: Bengio & Frasconi (1995)
- Online EM: Cappe & Moulines (2009)
- BOCD: Adams & MacKay (2007)
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

import numpy as np
from scipy import stats
from scipy.special import logsumexp, softmax, gammaln
import psycopg2
from psycopg2.extras import RealDictCursor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IOHMM_ONLINE")

# Database config
DB_CONFIG = {
    'host': os.environ.get('PGHOST', '127.0.0.1'),
    'port': int(os.environ.get('PGPORT', 54322)),
    'database': os.environ.get('PGDATABASE', 'postgres'),
    'user': os.environ.get('PGUSER', 'postgres'),
    'password': os.environ.get('PGPASSWORD', 'postgres')
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class StudentTParams:
    """Parameters for multivariate Student-t distribution"""
    mu: np.ndarray          # Mean vector (d,)
    sigma: np.ndarray       # Scale matrix (d, d)
    nu: float               # Degrees of freedom


@dataclass
class IOHMMConfig:
    """Configuration for IOHMM model"""
    n_states: int = 3
    n_features: int = 7
    n_covariates: int = 3
    state_labels: List[str] = field(default_factory=lambda: ['BULL', 'NEUTRAL', 'BEAR'])

    # Student-t parameters
    emission_nu: float = 5.0  # Default degrees of freedom

    # Online EM parameters
    learning_rate: float = 0.01
    learning_rate_decay: float = 0.999
    min_learning_rate: float = 0.001

    # BOCD parameters
    hazard_rate: float = 0.01
    changepoint_threshold: float = 0.5

    # Hysteresis
    hysteresis_days: int = 5


@dataclass
class IOHMMState:
    """Current state of IOHMM model"""
    # Emission parameters per state
    emission_params: List[StudentTParams]

    # Transition weights: shape (n_states, n_states, n_covariates + 1)
    # +1 for bias term
    transition_weights: np.ndarray

    # Initial state distribution
    initial_dist: np.ndarray

    # Online EM state
    learning_rate: float
    n_observations: int = 0

    # BOCD state
    run_length: int = 0
    changepoint_prob: float = 0.0


# =============================================================================
# STUDENT-T EMISSION
# =============================================================================

class StudentTEmission:
    """Multivariate Student-t emission distribution"""

    def __init__(self, params: StudentTParams):
        self.params = params
        self.d = len(params.mu)

    def log_prob(self, x: np.ndarray) -> float:
        """Compute log probability of observation under Student-t"""
        mu = self.params.mu
        sigma = self.params.sigma
        nu = self.params.nu
        d = self.d

        # Handle NaN values in observation
        valid_mask = ~np.isnan(x)
        if not np.any(valid_mask):
            return 0.0  # No valid observations

        x_valid = x[valid_mask]
        mu_valid = mu[valid_mask]

        # Reduce sigma to valid dimensions
        sigma_valid = sigma[np.ix_(valid_mask, valid_mask)]
        d_valid = len(x_valid)

        try:
            # Mahalanobis distance
            diff = x_valid - mu_valid
            sigma_inv = np.linalg.inv(sigma_valid + 1e-6 * np.eye(d_valid))
            mahal = diff @ sigma_inv @ diff

            # Log determinant
            sign, logdet = np.linalg.slogdet(sigma_valid)
            if sign <= 0:
                logdet = d_valid * np.log(1e-6)

            # Student-t log probability
            log_prob = (
                gammaln((nu + d_valid) / 2)
                - gammaln(nu / 2)
                - (d_valid / 2) * np.log(nu * np.pi)
                - 0.5 * logdet
                - ((nu + d_valid) / 2) * np.log(1 + mahal / nu)
            )

            return float(log_prob)

        except np.linalg.LinAlgError:
            return -1e10  # Very low probability on numerical error

    def update_params(self, x: np.ndarray, weight: float, learning_rate: float):
        """Online update of emission parameters"""
        valid_mask = ~np.isnan(x)
        if not np.any(valid_mask):
            return

        x_valid = x[valid_mask]
        mu_valid = self.params.mu[valid_mask]

        # Update mean with exponential moving average
        self.params.mu[valid_mask] = (
            (1 - learning_rate * weight) * mu_valid +
            learning_rate * weight * x_valid
        )

        # Update covariance (simplified diagonal update)
        diff = x_valid - self.params.mu[valid_mask]
        for i, idx in enumerate(np.where(valid_mask)[0]):
            old_var = self.params.sigma[idx, idx]
            new_var = (1 - learning_rate * weight) * old_var + learning_rate * weight * diff[i]**2
            self.params.sigma[idx, idx] = max(new_var, 1e-4)


# =============================================================================
# IOHMM TRANSITION MODEL
# =============================================================================

class IOHMMTransition:
    """
    Input-Output transition model.
    Transition probabilities are softmax of linear function of covariates.

    P(s_t = j | s_{t-1} = i, u_t) = softmax(W_i @ [u_t; 1])_j
    """

    def __init__(self, weights: np.ndarray, n_states: int):
        """
        Args:
            weights: Shape (n_states, n_states, n_covariates + 1)
            n_states: Number of hidden states
        """
        self.weights = weights
        self.n_states = n_states

    def get_transition_matrix(self, covariates: np.ndarray) -> np.ndarray:
        """
        Compute transition matrix given covariates.

        Args:
            covariates: Shape (n_covariates,) - macro factors

        Returns:
            Transition matrix shape (n_states, n_states)
        """
        # Add bias term
        u = np.append(covariates, 1.0)

        # Replace NaN with 0 in covariates
        u = np.nan_to_num(u, nan=0.0)

        trans_matrix = np.zeros((self.n_states, self.n_states))

        for i in range(self.n_states):
            # Linear combination: W_i @ u
            logits = self.weights[i] @ u
            # Softmax to get probabilities
            trans_matrix[i] = softmax(logits)

        return trans_matrix

    def update_weights(self, from_state: int, to_state: int,
                      covariates: np.ndarray, learning_rate: float):
        """Online update of transition weights using gradient ascent"""
        u = np.append(covariates, 1.0)
        u = np.nan_to_num(u, nan=0.0)

        # Current probabilities
        logits = self.weights[from_state] @ u
        probs = softmax(logits)

        # Gradient: u * (I[j=to_state] - p_j) for each j
        for j in range(self.n_states):
            target = 1.0 if j == to_state else 0.0
            gradient = u * (target - probs[j])
            self.weights[from_state, j] += learning_rate * gradient


# =============================================================================
# BAYESIAN ONLINE CHANGEPOINT DETECTION
# =============================================================================

class BOCDDetector:
    """
    Bayesian Online Changepoint Detection (Adams & MacKay, 2007)

    Maintains distribution over run length (time since last changepoint).
    """

    def __init__(self, hazard_rate: float = 0.01, max_run_length: int = 500):
        """
        Args:
            hazard_rate: Prior probability of changepoint at each time
            max_run_length: Maximum run length to track
        """
        self.hazard_rate = hazard_rate
        self.max_run_length = max_run_length

        # Run length distribution: P(r_t | x_{1:t})
        # r_t = 0 means changepoint just occurred
        self.run_length_probs = np.zeros(max_run_length + 1)
        self.run_length_probs[0] = 1.0  # Start with run length 0

        # Sufficient statistics for predictive distribution
        self.suff_stats = []

    def update(self, log_likelihood: float) -> Tuple[float, int]:
        """
        Update run length distribution given new observation.

        Args:
            log_likelihood: Log likelihood of observation under current model

        Returns:
            Tuple of (changepoint_probability, most_likely_run_length)
        """
        # Growth probabilities: P(r_t = r_{t-1} + 1 | ...)
        growth_probs = self.run_length_probs * (1 - self.hazard_rate)

        # Changepoint probability: P(r_t = 0 | ...)
        changepoint_prob = np.sum(self.run_length_probs * self.hazard_rate)

        # Shift and update
        new_probs = np.zeros_like(self.run_length_probs)
        new_probs[0] = changepoint_prob
        new_probs[1:] = growth_probs[:-1]

        # Weight by observation likelihood (simplified)
        # In full BOCD, would use UPM predictive likelihood per run length
        likelihood = np.exp(np.clip(log_likelihood, -100, 0))
        new_probs *= likelihood

        # Normalize
        total = np.sum(new_probs)
        if total > 0:
            new_probs /= total
        else:
            new_probs[0] = 1.0

        self.run_length_probs = new_probs

        # Most likely run length
        ml_run_length = int(np.argmax(self.run_length_probs))

        return float(changepoint_prob), ml_run_length

    def reset(self):
        """Reset detector after confirmed changepoint"""
        self.run_length_probs = np.zeros(self.max_run_length + 1)
        self.run_length_probs[0] = 1.0


# =============================================================================
# MAIN IOHMM CLASS
# =============================================================================

class IOHMM:
    """
    Input-Output Hidden Markov Model with Online EM and BOCD.
    """

    def __init__(self, config: IOHMMConfig):
        self.config = config
        self.state: Optional[IOHMMState] = None
        self.emissions: List[StudentTEmission] = []
        self.transition: Optional[IOHMMTransition] = None
        self.bocd: BOCDDetector = BOCDDetector(
            hazard_rate=config.hazard_rate
        )

        # Hysteresis tracking
        self.current_regime: Optional[str] = None
        self.regime_consecutive: int = 0
        self.regime_confirmed: bool = False

    def initialize(self, feature_dim: int = 7, covariate_dim: int = 3):
        """Initialize model with default parameters"""
        n_states = self.config.n_states

        # Initialize emission parameters (Student-t)
        emission_params = []
        for i in range(n_states):
            # Different initial means per state
            if i == 0:  # BULL
                mu = np.array([0.5, -0.3, 0.2, 0.3, -0.2, 0.3, 0.4])
            elif i == 1:  # NEUTRAL
                mu = np.zeros(feature_dim)
            elif i == 2:  # BEAR
                mu = np.array([-0.5, 0.5, -0.3, -0.3, 0.3, -0.3, -0.4])
            else:  # STRESS
                mu = np.array([-0.3, 1.0, -0.5, -0.2, 0.8, -0.2, -0.3])

            # Pad or truncate to feature_dim
            if len(mu) < feature_dim:
                mu = np.pad(mu, (0, feature_dim - len(mu)))
            mu = mu[:feature_dim]

            sigma = np.eye(feature_dim) * 1.0
            emission_params.append(StudentTParams(
                mu=mu,
                sigma=sigma,
                nu=self.config.emission_nu
            ))

        # Initialize transition weights (small random values)
        transition_weights = np.random.randn(
            n_states, n_states, covariate_dim + 1
        ) * 0.1

        # Add diagonal bias for persistence
        for i in range(n_states):
            transition_weights[i, i, -1] = 1.0  # Bias toward staying

        # Initial state distribution (uniform)
        initial_dist = np.ones(n_states) / n_states

        self.state = IOHMMState(
            emission_params=emission_params,
            transition_weights=transition_weights,
            initial_dist=initial_dist,
            learning_rate=self.config.learning_rate
        )

        # Create emission objects
        self.emissions = [StudentTEmission(p) for p in emission_params]

        # Create transition model
        self.transition = IOHMMTransition(transition_weights, n_states)

        logger.info(f"Initialized IOHMM with {n_states} states")

    def compute_emission_probs(self, features: np.ndarray) -> np.ndarray:
        """Compute emission log probabilities for all states"""
        log_probs = np.array([
            emission.log_prob(features) for emission in self.emissions
        ])
        return log_probs

    def forward_step(
        self,
        features: np.ndarray,
        covariates: np.ndarray,
        prev_alpha: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, float]:
        """
        Single forward step of forward algorithm.

        Args:
            features: Observation vector
            covariates: Macro covariate vector
            prev_alpha: Previous forward probabilities (or None for t=0)

        Returns:
            Tuple of (alpha_t, log_likelihood)
        """
        n_states = self.config.n_states

        # Emission probabilities
        log_emission = self.compute_emission_probs(features)

        if prev_alpha is None:
            # Initial step
            log_alpha = np.log(self.state.initial_dist + 1e-10) + log_emission
        else:
            # Get transition matrix for current covariates
            trans_mat = self.transition.get_transition_matrix(covariates)

            # Forward step: alpha_t(j) = sum_i alpha_{t-1}(i) * A(i,j) * B(j, x_t)
            log_alpha = np.zeros(n_states)
            for j in range(n_states):
                log_sum = logsumexp(
                    np.log(prev_alpha + 1e-10) + np.log(trans_mat[:, j] + 1e-10)
                )
                log_alpha[j] = log_sum + log_emission[j]

        # Normalize
        log_likelihood = logsumexp(log_alpha)
        alpha = np.exp(log_alpha - log_likelihood)

        return alpha, log_likelihood

    def decode_step(
        self,
        features: np.ndarray,
        covariates: np.ndarray,
        prev_alpha: Optional[np.ndarray] = None
    ) -> Tuple[int, np.ndarray, float]:
        """
        Decode most likely state for current observation.

        Returns:
            Tuple of (most_likely_state, state_posteriors, log_likelihood)
        """
        alpha, log_lik = self.forward_step(features, covariates, prev_alpha)

        # Most likely state from posterior
        most_likely = int(np.argmax(alpha))

        return most_likely, alpha, log_lik

    def online_em_update(
        self,
        features: np.ndarray,
        covariates: np.ndarray,
        state_posteriors: np.ndarray,
        prev_state: Optional[int] = None
    ):
        """
        Online EM update of model parameters.

        Args:
            features: Current observation
            covariates: Current covariates
            state_posteriors: Posterior probabilities P(s_t | x_{1:t})
            prev_state: Previous most likely state (for transition update)
        """
        lr = self.state.learning_rate

        # Update emission parameters
        for s, emission in enumerate(self.emissions):
            weight = state_posteriors[s]
            if weight > 0.01:  # Only update if meaningful weight
                emission.update_params(features, weight, lr)

        # Update transition weights
        if prev_state is not None:
            curr_state = int(np.argmax(state_posteriors))
            self.transition.update_weights(prev_state, curr_state, covariates, lr)

        # Decay learning rate
        self.state.learning_rate = max(
            self.config.min_learning_rate,
            self.state.learning_rate * self.config.learning_rate_decay
        )

        self.state.n_observations += 1

    def apply_hysteresis(self, raw_regime: str) -> Tuple[str, bool]:
        """
        Apply hysteresis filter to prevent regime flickering.

        Returns:
            Tuple of (filtered_regime, is_confirmed)
        """
        if raw_regime == self.current_regime:
            self.regime_consecutive += 1
        else:
            self.regime_consecutive = 1
            self.current_regime = raw_regime
            self.regime_confirmed = False

        if self.regime_consecutive >= self.config.hysteresis_days:
            self.regime_confirmed = True

        return self.current_regime, self.regime_confirmed

    def process_observation(
        self,
        features: np.ndarray,
        covariates: np.ndarray,
        prev_alpha: Optional[np.ndarray] = None,
        prev_state: Optional[int] = None,
        update_params: bool = True
    ) -> Dict[str, Any]:
        """
        Process single observation through full pipeline.

        Args:
            features: Technical feature vector
            covariates: Macro covariate vector
            prev_alpha: Previous forward probabilities
            prev_state: Previous most likely state
            update_params: Whether to update parameters via Online EM

        Returns:
            Dict with regime classification and diagnostics
        """
        # 1. Decode current state
        state_idx, posteriors, log_lik = self.decode_step(
            features, covariates, prev_alpha
        )

        # 2. BOCD update
        cp_prob, run_length = self.bocd.update(log_lik)

        # Check for changepoint
        is_changepoint = cp_prob > self.config.changepoint_threshold
        if is_changepoint:
            self.bocd.reset()
            # Increase learning rate temporarily after changepoint
            self.state.learning_rate = min(
                self.config.learning_rate * 2,
                0.1
            )
            logger.info(f"Changepoint detected! CP prob: {cp_prob:.3f}")

        # 3. Get raw regime label
        raw_regime = self.config.state_labels[state_idx]

        # 4. Apply hysteresis
        filtered_regime, is_confirmed = self.apply_hysteresis(raw_regime)

        # 5. Online EM update (if enabled and not during changepoint)
        if update_params and not is_changepoint:
            self.online_em_update(features, covariates, posteriors, prev_state)

        # Update BOCD state tracking
        self.state.run_length = run_length
        self.state.changepoint_prob = cp_prob

        return {
            'technical_regime': raw_regime,
            'sovereign_regime': filtered_regime,
            'regime_confidence': float(posteriors[state_idx]),
            'state_posteriors': posteriors.tolist(),
            'is_confirmed': is_confirmed,
            'consecutive_days': self.regime_consecutive,
            'changepoint_probability': cp_prob,
            'run_length': run_length,
            'is_changepoint': is_changepoint,
            'log_likelihood': log_lik,
            'alpha': posteriors  # For next iteration
        }


# =============================================================================
# DATABASE INTERFACE
# =============================================================================

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def load_model_from_db(conn, asset_class: str) -> Optional[IOHMM]:
    """Load IOHMM model from database"""
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Get config
    cur.execute("""
        SELECT * FROM fhq_perception.hmm_v4_config
        WHERE asset_class = %s AND is_active = TRUE
        LIMIT 1
    """, (asset_class,))

    config_row = cur.fetchone()
    if not config_row:
        logger.warning(f"No active config for {asset_class}")
        cur.close()
        return None

    config = IOHMMConfig(
        n_states=config_row['n_states'],
        state_labels=config_row['state_labels'],
        learning_rate=float(config_row['learning_rate']),
        hazard_rate=float(config_row['hazard_rate']),
        changepoint_threshold=float(config_row['changepoint_threshold']),
        hysteresis_days=config_row['hysteresis_days']
    )

    # Get saved model params
    cur.execute("""
        SELECT * FROM fhq_perception.hmm_model_params_v4
        WHERE asset_class = %s AND asset_id IS NULL
        ORDER BY last_updated_at DESC
        LIMIT 1
    """, (asset_class,))

    params_row = cur.fetchone()
    cur.close()

    model = IOHMM(config)

    if params_row and params_row['emission_mu']:
        # Load saved parameters
        try:
            emission_mu = params_row['emission_mu']
            emission_sigma = params_row['emission_sigma']
            emission_nu = params_row['emission_nu']
            transition_weights = np.array(params_row['transition_weights'])
            initial_dist = np.array(params_row['initial_dist'])

            emission_params = []
            for i in range(config.n_states):
                emission_params.append(StudentTParams(
                    mu=np.array(emission_mu[i]),
                    sigma=np.array(emission_sigma[i]),
                    nu=float(emission_nu[i]) if isinstance(emission_nu, list) else float(emission_nu)
                ))

            model.state = IOHMMState(
                emission_params=emission_params,
                transition_weights=transition_weights,
                initial_dist=initial_dist,
                learning_rate=float(params_row.get('learning_rate', config.learning_rate)),
                n_observations=params_row.get('trained_on_rows', 0),
                run_length=params_row.get('run_length', 0),
                changepoint_prob=float(params_row.get('changepoint_prob', 0))
            )

            model.emissions = [StudentTEmission(p) for p in emission_params]
            model.transition = IOHMMTransition(transition_weights, config.n_states)
            model.bocd = BOCDDetector(hazard_rate=config.hazard_rate)

            logger.info(f"Loaded model for {asset_class} with {model.state.n_observations} observations")

        except Exception as e:
            logger.error(f"Error loading saved params: {e}, initializing fresh")
            model.initialize()
    else:
        model.initialize()

    return model


def save_model_to_db(conn, model: IOHMM, asset_class: str):
    """Save IOHMM model to database"""
    if model.state is None:
        return

    cur = conn.cursor()

    # Prepare params as JSON
    emission_mu = [p.mu.tolist() for p in model.state.emission_params]
    emission_sigma = [p.sigma.tolist() for p in model.state.emission_params]
    emission_nu = [p.nu for p in model.state.emission_params]

    cur.execute("""
        INSERT INTO fhq_perception.hmm_model_params_v4 (
            asset_class, asset_id, n_states,
            emission_mu, emission_sigma, emission_nu,
            transition_weights, covariate_names, initial_dist,
            learning_rate, run_length, changepoint_prob,
            trained_on_rows, engine_version, last_updated_at
        ) VALUES (
            %s, NULL, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, 'v4.0.0', NOW()
        )
        ON CONFLICT (asset_class, asset_id) DO UPDATE SET
            emission_mu = EXCLUDED.emission_mu,
            emission_sigma = EXCLUDED.emission_sigma,
            emission_nu = EXCLUDED.emission_nu,
            transition_weights = EXCLUDED.transition_weights,
            initial_dist = EXCLUDED.initial_dist,
            learning_rate = EXCLUDED.learning_rate,
            run_length = EXCLUDED.run_length,
            changepoint_prob = EXCLUDED.changepoint_prob,
            trained_on_rows = EXCLUDED.trained_on_rows,
            last_updated_at = NOW()
    """, (
        asset_class,
        model.config.n_states,
        json.dumps(emission_mu),
        json.dumps(emission_sigma),
        json.dumps(emission_nu),
        json.dumps(model.state.transition_weights.tolist()),
        json.dumps(['yield_spread_z', 'vix_z', 'liquidity_z']),
        json.dumps(model.state.initial_dist.tolist()),
        model.state.learning_rate,
        model.state.run_length,
        model.state.changepoint_prob,
        model.state.n_observations
    ))

    conn.commit()
    cur.close()

    logger.info(f"Saved model for {asset_class}")


# =============================================================================
# TESTING
# =============================================================================

def initialize_model(config: IOHMMConfig, asset_class: str) -> IOHMM:
    """Initialize a new IOHMM model with given config"""
    model = IOHMM(config)

    # Determine feature/covariate dimensions based on asset class
    feature_dim = len(config.state_labels) + 4  # Base 7 features
    covariate_dim = 3  # yield_spread, vix, liquidity

    if asset_class == 'CRYPTO':
        feature_dim += 2  # on-chain features

    model.initialize(feature_dim=7, covariate_dim=3)  # Standard dimensions

    logger.info(f"Initialized new IOHMM model for {asset_class}")
    return model


def test_iohmm():
    """Test IOHMM with synthetic data"""
    logger.info("Testing IOHMM...")

    config = IOHMMConfig(
        n_states=3,
        state_labels=['BULL', 'NEUTRAL', 'BEAR'],
        learning_rate=0.05,
        hysteresis_days=3
    )

    model = IOHMM(config)
    model.initialize(feature_dim=7, covariate_dim=3)

    # Generate synthetic observations
    np.random.seed(42)
    n_obs = 100

    prev_alpha = None
    prev_state = None

    for t in range(n_obs):
        # Synthetic features (regime-dependent)
        true_regime = t // 33  # Changes every ~33 steps
        if true_regime == 0:  # BULL
            features = np.random.randn(7) * 0.5 + np.array([0.3, -0.2, 0.1, 0.2, -0.1, 0.2, 0.3])
        elif true_regime == 1:  # NEUTRAL
            features = np.random.randn(7) * 0.5
        else:  # BEAR
            features = np.random.randn(7) * 0.5 + np.array([-0.3, 0.3, -0.2, -0.2, 0.2, -0.2, -0.3])

        # Synthetic covariates
        covariates = np.random.randn(3) * 0.3

        result = model.process_observation(
            features, covariates, prev_alpha, prev_state
        )

        prev_alpha = result['alpha']
        prev_state = int(np.argmax(prev_alpha))

        if t % 20 == 0:
            logger.info(f"t={t}: regime={result['sovereign_regime']}, "
                       f"conf={result['regime_confidence']:.2f}, "
                       f"confirmed={result['is_confirmed']}")

    logger.info("IOHMM test complete")


if __name__ == '__main__':
    test_iohmm()
