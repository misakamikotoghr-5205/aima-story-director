# 展览导览：一件展品的两种讲法 — execution preparation

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

intro → detail

## Command plan

| Start ms | End ms | Command | Type | Planned content |
| ---: | ---: | --- | --- | --- |
| 0 | 7000 | intro:introduce | speech | 欢迎来到未来城市展台。眼前的节水模型，把一次普通的洗手，变成了一段可以观察的水循环。 |
| 800 | 4300 | intro:present | gesture | open-arms · amplitude 0.3 · speed 0.25 |
| 7000 | 9000 | intro:look | wait | Wait 2000 ms |
| 9000 | 9000 | intro:select-depth | branch | wants_detail == true |
| 9000 | 12000 | detail:point-filter | gesture | point-right · amplitude 0.25 · speed 0.25 |
| 9000 | 18000 | detail:explain-loop | speech | 右侧的透明容器代表过滤过程。模型中的蓝色小球代表水量，它们经过处理后，可以再次用于冲洗。这里只展示原理，不代表真实净化效果。 |
| 18000 | 20000 | detail:consider | wait | Wait 2000 ms |
| 20000 | 25000 | detail:question | speech | 如果把这个想法带回家，您会先从哪一种日常用水开始改变呢？ |

## Integrity

Source SHA256: `f52c05488ccb3e430c6265a34cd1a4a3d407091bf103445cc52dd85bc1c43e87`
Artifact manifest SHA256: `1524e92f2ac9562ce1cf5a57919e5fde5f946cb7d6cd395dc1456e52de02f575`

SHA256 checks detect accidental edits; this is not a signature or evidence of physical robot execution.
