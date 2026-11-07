# FIIL CC Pro2 离线激活 LDAC

FIIL+ 连不上官方激活服务时，可以用这个工具，通过电脑蓝牙给耳机激活 LDAC。整个过程可以离线完成，耳机固件也不用更换。

**目前只在国行 FIIL CC Pro2（F039）、固件 1.0.1.0 上实测成功。** 如果你的固件是 1.0.5.0 或其他版本，目前还不能确认能用，需要先分析验证。

## 开始前准备

- 一台带蓝牙的 Windows 电脑。
- Python 3.8 或以上版本。在 PowerShell 输入 `python --version` 能看到版本号即可。如果你的电脑用 `py -3` 启动 Python，下面所有命令里的 `python` 都换成 `py -3`。
- 在 FIIL+ 里查看耳机固件版本。本次实测使用的 App 是 FIIL+ 3.5.2。

下载本仓库并解压，在包含 `ccpro2_gaia.py` 的文件夹里打开 PowerShell。

## 激活步骤

**1. 让耳机连上电脑。**

两只耳机都从盒里取出，暂时关闭手机蓝牙，再到 Windows 蓝牙设置里配对并连接 FIIL CC Pro2。

**2. 找到耳机的蓝牙地址。**

在 PowerShell 执行下面的命令。

```powershell
pnputil.exe /enum-devices /connected /class Bluetooth |
  Select-String 'FIIL CC Pro2\s*$' -Context 1,0
```

找到耳机名称上方的设备信息。如果里面有 `BTHENUM\Dev_AABBCCDDEEFF\…`，那么蓝牙地址就是 `AABBCCDDEEFF`。这是示例地址，后面的命令都要换成你自己查到的地址。

**3. 先查一下当前状态。**

```powershell
python .\ccpro2_gaia.py status AABBCCDDEEFF
```

两行 `activation` 分别对应两耳，`0` 表示未激活，`1` 表示已激活。如果出现 `2`，说明暂时没拿到对侧耳机的状态，确认两耳都在盒外，等一会儿再查。

**4. 激活并打开 LDAC。**

```powershell
python .\ccpro2_gaia.py enable AABBCCDDEEFF --timeout 15
```

看到下面这句话，说明两耳都已激活，LDAC 开关也已打开。

```text
Both earbuds report LDAC activation and the switch is on.
```

耳机切换时可能会重启、断开一下，脚本会尝试重连。如果最后报超时，等耳机连回电脑，再执行一次 `status`。两耳都是 `1`，并且显示 `LDAC switch: 1`，就是成功了。

## 连回手机确认

断开电脑蓝牙，让耳机连回手机，播放一首歌。FIIL+ 页面应显示 LDAC 开关已打开，状态为「高清」。

在小米 14 上，还可以进入「设置 → 更多设置 → 开发者选项 → 蓝牙音频编解码器」，确认播放时选中的是 LDAC。如果蓝牙设备详情里有「高清音频」或「LDAC」开关，也要打开。

开启 LDAC 后，耳机会变为单点连接，游戏低延时模式也会关闭。

## 遇到问题

- **提示 `RFCOMM connect failed`**，先确认耳机确实连在这台电脑上，手机蓝牙已关闭，命令里的地址也已替换。
- **只有一耳激活成功**，确认两耳都已连好，再运行 `enable`。脚本会跳过已经激活的一耳。
- **已经激活，但开关还是 `0`**，重新运行 `enable`，它会继续尝试打开 LDAC。
- **想关掉 LDAC**，执行下面的命令，激活状态会保留。

```powershell
python .\ccpro2_gaia.py off AABBCCDDEEFF
```

排查时可以在命令后加 `--verbose` 查看详细收发记录，或用 `--help` 查看全部命令。

## 方法是怎么找到的

先反编译 FIIL+，找到它发给耳机的蓝牙指令，再从耳机读取固件并反汇编。在主控程序里找到一个能让耳机自行生成、保存激活数据的分支，随后通过蓝牙逐耳调用，并查询状态确认成功。

具体的指令和固件分析过程放在 [技术说明](skills/earbuds-firmware-reverse/references/fiil-cc-pro2.md)。

## 让 Agent 分析其他耳机

仓库附带 [earbuds-firmware-reverse skill](skills/earbuds-firmware-reverse/SKILL.md)。把整个 `skills/earbuds-firmware-reverse` 文件夹复制到用户目录的 `.codex/skills/`，在 Codex 新会话里调用，并提供耳机型号、固件版本和 APK 或固件文件。

```text
使用 $earbuds-firmware-reverse 分析这副耳机的离线激活方法。
型号是 FIIL CC Pro2，固件是 1.0.5.0，相关文件在当前工作区。
先分析这个版本是否保留了本地激活逻辑，再判断能否使用已有方法。
```

这个 skill 提供分析流程。其他型号和固件的激活方法，要根据各自的固件重新确认。
