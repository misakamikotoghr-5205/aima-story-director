# Hardware adapter contract — preparation only

The shipped `DryRunAdapter` always returns `status: simulated` and `hardware_sent: false`. There is no implemented hardware adapter, background discovery, network connection, TTS engine, microphone, camera, or motor-control code.

## Inputs available from the director

Each planned command contains:

- `command_id`: stable `scene:step` identifier.
- `type`: `speech`, `gesture`, `wait`, or `branch`.
- `start_ms` and `end_ms`: authored simulation timing in milliseconds from show start.
- `parameters`: the validated semantic action fields.
- `scene_id` and `scene_label`: context for logging and operator review.

A future device adapter must acknowledge real command acceptance, completion, interruption, and failures. A simulated receipt must never be renamed to imply hardware success. Authored `duration_ms` values must be reconciled with actual speech/motion completion before a scheduler can preserve timing on a robot.

## Required device-specific decisions

1. Confirm the robot model, firmware, supported protocol, permissions, resource catalog, and interruption semantics.
2. Map semantic gesture names to installed, compatible motion resources. Normalized `amplitude` and `speed` are preview parameters and cannot be passed directly as physical joint limits.
3. Define ownership of the speech and movement channels when other robot software is active.
4. Decide how operators can pause/stop, how a disconnect affects in-progress commands, and how real acknowledgements are audited.
5. Implement and verify live event inputs separately. The current fixture is a constant test snapshot; `distance_near` is not produced by a sensor or a safety system.
6. Validate the robot, venue, and show with the responsible operator before physical use.

## Official references checked November 4, 2026

- [AIMA creator activity / Linkcraft](https://linkcraft.agibot.com/?activityPage=page2&locale=zh-CN&page=activity): reference destination supplied by the user. This repository has not been uploaded to the platform or accepted into the program.
- [AimDK A2 v1.2 SDK usage](https://open.agibot.com/docs/aimdk/a2/v1_2/getting_started/sdk_usage): model-specific RPC/channel documentation and protocol sources.
- [AimDK A2 v1.2 interaction guide](https://open.agibot.com/docs/aimdk/a2/v1_2/getting_started/interaction2): interaction extension modes and speech-related interfaces.
- [A3-Ultra v3.3 skill playback](https://open.agibot.com/docs/aimdk/a3-ultra/v3_3/dev_guide/07-10-skill_poilt): resource-based motion playback for that model/version.

The project intentionally does not choose one of those protocols without a matching device. No undocumented AIMA endpoints, upload protocols, or universal gesture resource IDs are claimed.
