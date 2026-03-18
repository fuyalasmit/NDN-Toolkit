### Normal Traffic dataset:

- logs1
- logs_mesh1
- logs_dumbbell1

### Interest Flooding Attack [Fake Interest]

- logs_dumbbell_ifa
  - c1, c2, c3 -> r1 -> r2 -> bottleneck -> r3 -> r4 -> p1, p2
  - p1 and p2 are normal producers while c1, c2, and c3 are consumer at first
  - `later c1 becomes attacker`

### Cache Pollution Attack [Unpopular content]

- logs_tree_cp
  - p1 is legitimate producer
  - `p2 is malicious producer`

`Note:` Normal producers publish legitimate content names, and normal consumers request that content to create realistic background traffic. In attack scenarios, the malicious traffic does not start immediately; it begins only after a warm-up period, so the same log file contains both normal baseline behavior and the later attacked behavior for comparison.

- The dataset has both normal and anamoly but we don't have exact time to seperate them both.
- A bottleneck router is the router (or forwarding point) where network capacity is most limited, so traffic queues up there first under load.
- In your Dumbbell topology, bottleneck is the middle router/link between consumer-side routers and producer-side routers, and it has limited bandwidth. That means:
  - Many flows must pass through it.
  - Its PIT/forwarding resources get stressed earlier than other nodes.
  - During interest flooding, congestion and unsatisfied Interests become most visible around this point.

### Understanding the dataset:

The dataset contains three files:

- `anomaly_traffic_features.csv`
- This contains only the data from two files `logs_dumbbell_ifa` and `logs_tree_cp`
- The respective node of each file while is behaving as anomlay is flagged as such. Rest is normal
- Contains normal traffic data from three files `logs1`,`logs_mesh1` and `logs_dumbbell1`
- `ndn_mixed_normal_anomaly_features.csv`
  - mixed data from all logs, labeled aswell.
- `normal_traffic_features.csv`
  - contains only normal traffic, use for initial training of model
- `cp_attack_features.csv`
  - this contains data of content poisioning attack
- `ifa_attack_features.csv`
  - the interest flooding attack dataset

### Initial Features

- timestamp: Time when that metric snapshot was recorded.
- node: Node name that produced the snapshot (for example c1, r2, bottleneck).
- nPitEntries: Current number of PIT entries (pending unsatisfied Interests).
- nInInterests: Total Interests received by the node.
- nOutInterests: Total Interests forwarded/sent out by the node.
- nInData: Total Data packets received by the node.
- nInNacks: Total NACK packets received by the node.
- nOutNacks: Total NACK packets sent by the node.
- nSatisfiedInterests: Interests that were successfully satisfied by Data.
- nUnsatisfiedInterests: Interests that expired or failed without Data.
- nCsEntries: Current number of entries in Content Store (cache).
- nHits: Cache hits (requested Data found in Content Store).
- nMisses: Cache misses (requested Data not found in Content Store).

### Engineered Features:

- pit_size: Current number of pending Interests in PIT (queue pressure right now).
- pit_growth_rate: Per-second change in PIT size (how fast pending load is building or draining).
- cs_size: Current number of entries in Content Store (cache occupancy).
- cache_hit_ratio: Fraction of requests served from cache: hits / (hits + misses).
- satisfaction_ratio: Fraction of Interests successfully satisfied by Data.
- unsatisfied_ratio: Fraction of Interests not satisfied (timeouts/failures).
- in_interests_rate: Per-second rate of incoming Interests.
- out_interests_rate: Per-second rate of forwarded outgoing Interests.
- in_data_rate: Per-second rate of incoming Data packets.
- nack_rate: Per-second rate of NACK activity (incoming + outgoing NACK changes).
