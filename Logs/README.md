
# Mini-NDN Log Archive

This directory contains raw log archives collected from long-running Mini-NDN simulations under both normal and attack conditions. The README is intentionally focused on the dataset and experiment architecture rather than the orchestration scripts.

## Archive Summary

| Archive | Scenario | Topology | Notes |
| --- | --- | --- | --- |
| `logs.tar.gz` | Normal traffic | Tree-12 | About 30 minutes of simulation, nodes logged every 5 seconds. |
| `logs1.tar.gz` | Normal traffic | Tree-12 | Longer tree run, roughly 2 hours, nodes logged every 2 seconds. |
| `logs_mesh1.tar.gz` | Normal traffic | DFN-12 | Long-running mesh-style simulation with dense logs. |
| `logs_dumbbell1.tar.gz` | Normal traffic | Dumbbell-12 | Baseline run on the dumbbell topology. |
| `logs_dumbbell_ifa.tar.gz` | Interest flooding attack | Dumbbell-12 | Normal traffic first, then a low-rate multi-prefix fake Interest attack through the bottleneck. |
| `logs_tree_cp.tar.gz` | Cache pollution attack | Tree-based topology | Normal traffic first, then cache pollution using unpopular content under `/ndn/pollution/*`. |

## Common Experiment Architecture

All scenarios follow the same high-level structure:

1. The Mini-NDN topology is started and routing is allowed to converge.
2. Every node runs NFD and NLSR.
3. NFD metrics are collected periodically and written to log folders.
4. Legitimate producers advertise normal NDN prefixes.
5. Legitimate consumers generate background demand for those prefixes.
6. In anomaly runs, malicious traffic is introduced only after a warm-up period so the logs contain both baseline and attacked behavior.

This makes the attack archives useful for comparing pre-attack and during-attack forwarding behavior in the same run.

## Attack Architecture

### 1. Interest Flooding Attack: `logs_dumbbell_ifa.tar.gz`

This scenario runs on the Dumbbell-12 topology, where the consumer side and producer side are connected through a narrow bottleneck. That topology is useful for interest flooding because it concentrates contention on a small number of forwarding links.

High-level layout:

```text
c1, c2, c3 -> r1 -> r2 -> bottleneck -> r3 -> r4 -> p1, p2
```

Architecture during the attack:

- `p1` and `p2` act as legitimate producers for the normal `/ndn` namespace.
- `c1`, `c2`, and `c3` generate legitimate consumer traffic during the baseline phase.
- After the normal phase stabilizes, `c1` also becomes the attacker and starts sending fake Interests.
- The fake Interests are pushed across the bottleneck, which increases PIT pressure and forwarding load on the shared path used by legitimate traffic.
- Because the attack uses multiple fake names with different lifetimes, the pending state is not concentrated on a single prefix.

Fake Interest profile from `traffic-client-fake.conf`:

| Traffic share | Name | InterestLifetime |
| --- | --- | --- |
| 40% | `/ndn/fake/video` | 2000 ms |
| 30% | `/ndn/random-attack` | 1500 ms |
| 20% | `/ndn/fake/image` | 1000 ms |
| 10% | `/ndn/random-attack-2` | 4000 ms |

What this architecture is meant to stress:

- The bottleneck link between the consumer side and producer side.
- PIT occupancy on routers that forward both normal and fake Interests.
- The impact of unsatisfied or low-value Interests on legitimate flow completion and forwarding efficiency.

### 2. Cache Pollution Attack: `logs_tree_cp.tar.gz`

This scenario runs on a tree-style topology and separates the roles of the legitimate producer and the malicious producer. The goal is to keep normal demand active while poisoning router caches with unpopular content.

Architecture during the attack:

- `p1` is the legitimate producer and serves the normal `/ndn` namespace.
- `p2` is the malicious producer and advertises `/ndn/pollution`.
- Legitimate consumers continue requesting normal content from `/ndn`.
- Attack consumers `c1` and `c6` request many low-value names under `/ndn/pollution/*`.
- These unpopular Data packets travel through shared routers and compete for cache space with legitimate content.

Pollution content served by `traffic-junk.conf`:

| Prefix set | ContentBytes | FreshnessPeriod |
| --- | --- | --- |
| `/ndn/pollution/random` | 1024 bytes | 1000 ms |
| `/ndn/pollution/random-1` to `/ndn/pollution/random-99` | 512 bytes each | 1000 ms |

Attack request pattern from `traffic-junk-client.conf`:

| Requested names | TrafficPercentage | InterestLifetime |
| --- | --- | --- |
| `/ndn/pollution/random` | 1.00 | 2000 ms |
| `/ndn/pollution/random-1` to `/ndn/pollution/random-99` | 1.00 each | 2000 ms |

Interpretation of the cache pollution architecture:

- The attack spans 100 unpopular objects in total: one `random` object and `random-1` through `random-99`.
- The attacker demand is spread evenly across many names instead of repeatedly requesting one object.
- This pattern reduces cache usefulness by filling the content store with objects that normal users are unlikely to request again.
- The expected effect is lower cache hit ratio, more upstream fetches, and degraded performance for the legitimate `/ndn` workload.

## Topology Reference

To visualize these topologies, open https://play.ndn.today/?default=1. In the left sidebar, use `Import/Export`, choose `MiniNDN Config`, paste one of the following definitions, and import it.

### Tree-12 topology

```ini
[nodes]
p1: _ radius=0.3 angle=0
p2: _ radius=0.3 angle=3.14
r1: _ radius=0.6 angle=0.8
r2: _ radius=0.6 angle=2.3
r3: _ radius=0.6 angle=4.0
r4: _ radius=0.6 angle=5.5
c1: _ radius=1.0 angle=0.5
c2: _ radius=1.0 angle=1.2
c3: _ radius=1.0 angle=2.0
c4: _ radius=1.0 angle=2.8
c5: _ radius=1.0 angle=3.6
c6: _ radius=1.0 angle=4.4

[links]
p1:r1 delay=10ms
p2:r1 delay=10ms
r1:r2 delay=10ms
r1:r3 delay=10ms
r2:r4 delay=10ms
r3:r4 delay=10ms
r2:c1 delay=10ms
r2:c2 delay=10ms
r3:c3 delay=10ms
r3:c4 delay=10ms
r4:c5 delay=10ms
r4:c6 delay=10ms
```

### DFN-12 topology

```ini
[nodes]
p1: _ radius=0.3 angle=0
p2: _ radius=0.3 angle=3.14
r1: _ radius=0.6 angle=0.8
r2: _ radius=0.6 angle=2.3
r3: _ radius=0.6 angle=4.0
r4: _ radius=0.6 angle=5.5
c1: _ radius=1.0 angle=0.5
c2: _ radius=1.0 angle=1.2
c3: _ radius=1.0 angle=2.0
c4: _ radius=1.0 angle=2.8
c5: _ radius=1.0 angle=3.6
c6: _ radius=1.0 angle=4.4

[links]
p1:r1 delay=10ms
p2:r1 delay=10ms
r1:r2 delay=10ms
r1:r3 delay=10ms
r2:r4 delay=10ms
r3:r4 delay=10ms
r2:c1 delay=10ms
r2:c2 delay=10ms
r3:c3 delay=10ms
r3:c4 delay=10ms
r4:c5 delay=10ms
r4:c6 delay=10ms
r1:r4 delay=15ms
r2:r3 delay=15ms
```

### Dumbbell-12 topology

```ini
[nodes]
c1: _ radius=0.3 angle=0.5
c2: _ radius=0.3 angle=1.0
c3: _ radius=0.3 angle=1.5
r1: _ radius=0.6 angle=0.8
r2: _ radius=0.6 angle=1.2
bottleneck: _ radius=1.0 angle=1.57
r3: _ radius=1.4 angle=2.0
r4: _ radius=1.4 angle=2.5
p1: _ radius=1.7 angle=2.8
p2: _ radius=1.7 angle=3.2

[links]
c1:r1 delay=10ms
c2:r1 delay=10ms
c3:r1 delay=10ms
r1:r2 delay=10ms
r2:bottleneck delay=10ms bw=10
bottleneck:r3 delay=10ms bw=10
r3:r4 delay=10ms
r3:p1 delay=10ms
r4:p2 delay=10ms
```

## Notes

- The normal archives are useful as baselines for the same forwarding stack without malicious traffic.
- The attack archives are designed to capture both the steady state before the attack and the degraded state after the attack starts.
- If you later want this README to include metric interpretation guidance, I can add a section describing which log fields are most useful for detecting IFA and cache pollution.