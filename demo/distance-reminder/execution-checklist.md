# 友好距离提醒：请给彼此一点空间 — execution preparation

**Mode: dry-run. Hardware commands sent: 0.**

This is a planning artifact. A robot adapter, an authorized device connection, and verified device resources are not provided.

## Before any separately implemented hardware deployment

- [ ] Select the exact robot model, firmware, and matching vendor protocol documentation.
- [ ] Obtain authorized device access and map semantic gestures to supported device resources.
- [ ] Validate speech duration and motion completion against device acknowledgements; these timings are authored estimates.
- [ ] Supply live event sources; this preview uses a fixed event fixture, not robot sensors.
- [ ] Test interruption, stop, disconnect, resource conflicts, and operator control on the actual device.
- [ ] Review the venue and device operating requirements with the responsible operator.

## Selected route

check → remind → ask-operator

## Command plan

| Start ms | End ms | Command | Type | Planned content |
| ---: | ---: | --- | --- | --- |
| 0 | 500 | check:settle | wait | Wait 500 ms |
| 500 | 500 | check:choose-reminder | branch | distance_near == true |
| 500 | 5500 | remind:request-space | speech | 我们离得有一点近。请您向后稍退一步，让我们都更从容地交流，谢谢您。 |
| 5500 | 8500 | remind:allow-time | wait | Wait 3000 ms |
| 8500 | 8500 | remind:check-response | branch | space_restored == true |
| 8500 | 13500 | ask-operator:pause-conversation | speech | 我先暂停讲解。请现场工作人员帮我们安排合适的交流位置，谢谢。 |
| 13500 | 18500 | ask-operator:wait-for-help | wait | Wait 5000 ms |

## Integrity

Source SHA256: `b87f0e957ce9a692d10012441effd766e50b292608b61cb76639c467ba0653bb`
Artifact manifest SHA256: `d64a46b30851f38ba6838a9d147f194bf1bf1e9c02fa3048b3a2318d8264fe38`

SHA256 checks detect accidental edits; this is not a signature or evidence of physical robot execution.
