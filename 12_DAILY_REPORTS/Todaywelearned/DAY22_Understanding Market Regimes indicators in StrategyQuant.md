FjordHQ trenger en ekspert vurdering om dette bør settes opp i databasen mot Korrekt Regime IoS-003, samt tilhørende G0-G4 i ADR-004 change gates. 



Understanding Market Regimes indicators in StrategyQuant Coding Base
Over the past few months, we have added several technical indicators to our coding base. When selecting these indicators, we focused on ensuring that they help users better identify market regimes.

In the first part of this article, we will briefly explain what market regimes are. In the second part, we will discuss how to configure each of these indicators and how to effectively use them during strategy development.

 

What Are Market Regimes?
Market regimes are distinct periods where markets exhibit specific statistical properties. Beyond simple “bull” and “bear” classifications, markets operate in multiple states:

Trending markets with persistent directional movement
Range-bound markets where prices oscillate within boundaries
High-volatility periods featuring large price swings
Low-volatility periods with minimal price movement
Correlation shifts between related instruments
Liquidity variations affecting execution quality
A critical insight for StrategyQuant users: strategies optimized for one regime typically underperform when conditions change. This explains why a profitable strategy can suddenly start losing without any code changes.

Why Your Strategies Suddenly Stop Working
Strategy failure usually isn’t due to flawed logic but to undetected market regime changes. Consider these common scenarios:

Your trend-following system that performed beautifully for months suddenly accumulates losses when markets become choppy
Your breakout strategy that captured major moves now faces repeated false signals
Your mean-reversion setup that thrived in range-bound conditions gets steamrolled when strong trends emerge
Standard indicators like moving averages, RSI, or Bollinger Bands typically don’t detect these fundamental shifts until significant losses occur. They track symptoms rather than identifying underlying statistical changes in market behavior.

​Enhancing StrategyQuant with Advanced Statistical Regime Detection
StrategyQuant platform users gain access to four advanced statistical indicators specifically designed for market regime detection:

Kolmogorov-Smirnov Test – Detects statistically significant changes in price distribution
Wasserstein Distance – Measures the magnitude of distribution shifts
CUSUM (Cumulative Sum) – Identifies subtle, persistent changes in market behavior
DTW (Dynamic Time Warping) – Recognizes similar pattern formations regardless of timeframe stretching
These tools evaluate fundamental aspects of market behavior that conventional indicators miss:

Changes in return distributions
Shifts in temporal structure
Pattern similarities with historical periods
Persistence of deviations from established norms
Practical Applications in StrategyQuant
For StrategyQuant users, these indicators can help you in theese situations:

Strategy Switching – Create custom blocks in your strategies that activate different trading logic based on detected regimes
Parameter Adaptation – Automatically adjust stop-loss, take-profit, and position sizing based on current market conditions
Portfolio Allocation – Shift capital between strategies optimized for different regimes
Robust Backtesting – Test strategies across multiple detected regimes to ensure consistent performance
Forward Testing Validation – Compare current market conditions with historical regimes to better validate forward testing results
The following sections will show you exactly how to configure each indicator within StrategyQuant to detect regime changes before they impact your trading performance.

 

Market Regime Indicators in StrategyQuant Coding Base
In the following section, we will look at how to properly set up and use each indicator.

Setting Up the Kolmogorov-Smirnov Test Indicator
The KS Test compares recent price action against historical distributions to detect statistically significant changes. Here’s how to set it up effectively:

Key Parameters
Period1 (Recent Sample Size): This defines how many recent bars will be analyzed.

Start with 20-30 bars for daily charts
Use 50-100 bars for intraday charts
Larger values (50-100) provide more statistical confidence but respond more slowly to changes
Period2 (Historical Sample Size): This determines the historical reference period.

Generally set equal to or larger than Period1
A good starting point is setting Period2 = Period1
For more sensitivity to recent changes, make Period2 larger (e.g., 2-3x Period1)
SignalThreshold: The statistical significance level.

The default value of 0.05 (5%) is standard in statistics
Lower values (0.01) reduce false signals but might miss some regime changes
Higher values (0.10) increase sensitivity but generate more false signals
Practical Setup Examples
Conservative Setup:

Period1 = 50
Period2 = 100
SignalThreshold = 0.01
Best for: Weekly or daily charts, lower frequency trading
Balanced Setup:

Period1 = 30
Period2 = 50
SignalThreshold = 0.05
Best for: Daily charts, swing trading
Responsive Setup:

Period1 = 20
Period2 = 30
SignalThreshold = 0.10
Best for: Intraday charts, more frequent signals
Interpretation Guidelines
When the indicator value is 1, it suggests a statistically significant regime change
Look for persistent signals (multiple consecutive 1s) rather than isolated instances
Combine with other indicators to confirm the change
​You can download the indicator and custom blocks here.

Setting Up the Wasserstein Distance Indicator
Wasserstein Distance measures the dissimilarity between recent and historical price distributions on a continuous scale.

Key Parameters
Period: This defines the window size for comparison.

Start with 20-50 bars for most timeframes
Shorter periods (20-30) react more quickly to distribution changes
Longer periods (50-100) provide more stable readings but lag in detection
Practical Setup Examples
Fast-Response Setup:

Period = 20
Best for: Catching quick regime transitions, intraday trading
Standard Setup:

Period = 50
Best for: Daily charts, balanced between responsiveness and stability
Trend-Focused Setup:

Period = 100
Best for: Identifying major regime shifts while filtering noise, weekly charts
Interpretation Guidelines
The indicator provides values on a 0-100 scale
Typically, values below 20 indicate similar distributions (same regime)
Values of 40+ suggest significant distribution differences
Watch for sustained increases in the indicator value rather than brief spikes
Establish baseline readings during known market regimes for your specific instrument
​You can download the indicator and custom blocks here.

Setting Up the CUSUM Indicator
CUSUM detects subtle, persistent changes in price behavior by accumulating deviations.

Key Parameters
Period: The lookback period for calculating mean and standard deviation.

Start with 20-50 bars
Shorter periods are more responsive to recent changes
Longer periods create more stable reference statistics
Threshold: Controls sensitivity to deviations.

Default value of 2 corresponds to 2 standard deviations
Lower values (1-1.5) increase sensitivity and generate more signals
Higher values (2.5-3) reduce false alarms but might delay detection
Drift: Accounts for expected natural drift in the process.

Default value of 0.5 is suitable for most markets
Increase drift (0.7-1.0) in more volatile markets
Decrease drift (0.2-0.3) in less volatile, range-bound markets
Practical Setup Examples
Early Warning Setup:

Period = 20
Threshold = 1.5
Drift = 0.3
Best for: Getting ahead of regime changes, accepting some false positives
Balanced Setup:

Period = 50
Threshold = 2
Drift = 0.5
Best for: Most market conditions, daily timeframes
Confirmation Setup:

Period = 100
Threshold = 3
Drift = 0.5
Best for: Confirming established regime changes, reducing false signals
Interpretation Guidelines
Monitor both Positive and Negative CUSUM lines
When either line rises significantly above zero, it indicates a potential regime change
Positive CUSUM rising suggests upward pressure/regime shift
Negative CUSUM rising suggests downward pressure/regime shift
The longer a CUSUM line stays elevated, the stronger the signal
Reset your expectations when both lines return to near zero
​You can download the indicator and custom blocks here.

 

Setting Up the Dynamic Time Warping Indicator
DTW identifies similar patterns in price action regardless of timeframe stretching or compression.

Key Parameters
WindowSize: The lookback period to search for patterns.

Start with 20-50 bars
Larger windows (50+) allow for finding more distant patterns
Smaller windows focus on recent market behavior
PatternSize: The length of the pattern to match.

Start with 5-10 bars
Shorter patterns (3-5) identify micro-structures
Longer patterns (10-20) identify larger market formations
DistanceType: The method used to calculate differences.

Absolute (0): More robust to outliers, recommended for most cases
Squared (1): More sensitive to large deviations, useful for detecting volatility regime changes
Practical Setup Examples
Micro-Pattern Setup:

WindowSize = 20
PatternSize = 5
DistanceType = 0 (Absolute)
Best for: Short-term trading, identifying quick repeating patterns
Standard Setup:

WindowSize = 30
PatternSize = 10
DistanceType = 0 (Absolute)
Best for: Most trading timeframes and instruments
Macro-Pattern Setup:

WindowSize = 50
PatternSize = 15
DistanceType = 1 (Squared)
Best for: Longer-term analysis, identifying major market structures
Interpretation Guidelines
Lower DTW values indicate similarity to historical patterns (regime continuity)
Sudden increases suggest unfamiliar price action (potential regime change)
Look for unusually low values to identify strongly repeating patterns
Establish baseline readings specific to your market and timeframe
​You can download the indicator and custom blocks here.

Combining Indicators for a Complete Regime Detection System
For the most robust regime detection, consider these multi-indicator approaches:

Early Warning System
Start with CUSUM (sensitive setup) for first alert
When CUSUM signals, check Wasserstein Distance for confirmation
Use KS Test as final statistical validation
Strength-of-Change Measurement
Use KS Test to determine if a statistically significant change has occurred
Measure Wasserstein Distance to quantify how different the new regime is
Monitor DTW to identify if the new pattern resembles any historical regimes
Timeframe Integration
Apply indicators across multiple timeframes
Look for confluence of signals (e.g., KS Test signaling on both daily and weekly)
Short-term indicators can provide early warnings for longer-term regime shifts
Practical Considerations for All Indicators
Market-Specific Adjustments
Equities: Generally less volatile; use more sensitive settings

Reduce KS Test threshold to 0.03-0.04
Reduce CUSUM threshold to 1.5-2.0
Forex: Regime changes can be subtle; focus on early detection

Use shorter periods across all indicators
Monitor CUSUM closely for early warning
Commodities: Often exhibit sharp regime transitions; need robust confirmation

Use KS Test with stricter threshold (0.01-0.03)
Increase Wasserstein Distance period for stability
Cryptocurrencies: Highly volatile; need filtering of false signals

Use longer periods across all indicators
Increase CUSUM threshold to 2.5-3.0
Regular Recalibration
For optimal performance, recalibrate your indicators:

Every 3-6 months for most markets
After significant market events (crashes, major news)
When you notice deterioration in signal quality
Final Thoughts on Implementation
Remember that market regime indicators are most powerful when:

Used in combination rather than isolation
Calibrated specifically to your trading instruments and timeframes
Integrated into a complete trading approach rather than used as standalone signals
Regularly reviewed and adjusted as market conditions evolve