# Diagnostic product strategy

ROS Developer Studio is an engineering investigation tool. A chart, message tree or sensor canvas is useful only when it helps answer: **what failed, when did it fail, what evidence supports that conclusion, and what should the engineer check next?**

## Investigation loop

1. **Observe:** collect live or recorded samples with their source and distinct header, receive and record timestamps.
2. **Detect:** identify factual anomalies such as missing publishers, incompatible QoS, rate changes, gaps, stale data, invalid values, malformed TF and resource pressure.
3. **Correlate:** align anomalies from topics, logs, diagnostics, TF and host metrics on one timeline.
4. **Explain:** show evidence separately from possible causes. Never present a guess as a confirmed root cause.
5. **Verify:** suggest concrete checks and let the engineer mark a hypothesis as confirmed or rejected for the report.

## Shared live and bag behavior

Selecting a bag makes it the active offline evidence source. Inspector, Signals, Motion, Visualizations, TF and Findings should consume the same normalized samples and the same global cursor. Seeking or pausing in any page changes the shared offline session. Offline playback reads files directly and never publishes into ROS.

Live and recorded measurements must stay labelled. Live frequency uses agent receive time. Bag frequency and gaps use record time, with header time shown separately when available.

## Finding contract

Every finding contains:

- severity and affected component;
- the measured symptom, timestamps and values that triggered it;
- the rule or user expectation used;
- plausible causes, clearly labelled as hypotheses;
- suggested checks that can confirm or reject each hypothesis;
- links to the relevant timeline range, messages, logs, TF frames or host samples.

Generic rules may rely only on ROS contracts and measured baselines. Robot-specific limits such as expected scan rate, motor tracking tolerance, battery voltage, frame availability or command-to-motion delay must come from an explicit diagnostic profile configured by the user.

## Product priorities

1. Shared offline data source and global timeline across analysis pages.
2. Evidence-based findings for live and bag sources.
3. Cross-topic and cross-source correlation around an incident window.
4. User-defined expectations and reusable diagnostic profiles.
5. Investigation reports containing evidence, hypotheses, checks and conclusions.

New visualizations should be added only when they support one of these investigation tasks.
