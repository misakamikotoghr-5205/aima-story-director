# 迎宾：第一次见面的三十秒 — execution preparation

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

arrival → greeting → directions

## Command plan

| Start ms | End ms | Command | Type | Planned content |
| ---: | ---: | --- | --- | --- |
| 0 | 1000 | arrival:observe | wait | Wait 1000 ms |
| 1000 | 1000 | arrival:choose-welcome | branch | visitor_present == true |
| 1000 | 6000 | greeting:hello | speech | 您好，欢迎来到今天的开放日。我是门口的迎宾伙伴，很高兴见到您。 |
| 1500 | 4000 | greeting:small-wave | gesture | wave · amplitude 0.35 · speed 0.3 |
| 6500 | 10500 | greeting:offer-help | speech | 您可以先到签到台领取地图。需要我介绍展区方向吗？ |
| 11000 | 11000 | greeting:choose-help | branch | needs_directions == true |
| 11000 | 14000 | directions:point | gesture | point-left · amplitude 0.3 · speed 0.25 |
| 11000 | 17000 | directions:guide | speech | 签到台在您左手边的蓝色标识处。前方的志愿者也会帮助您，祝您参观愉快。 |

## Integrity

Source SHA256: `8986b37a2691ac41bace70dde2289159f76453d4b95fc7f0947d6a32a7da067f`
Artifact manifest SHA256: `f41d359758517314634a3c91def9bb87ea961438bbc8395c9dae546e2f2194db`

SHA256 checks detect accidental edits; this is not a signature or evidence of physical robot execution.
