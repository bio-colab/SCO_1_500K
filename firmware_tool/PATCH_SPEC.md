# SCO_1_500K Firmware Patch Specification & Disassembly Guide
# التوثيقا الهندسي الشامل لباتشات الفيرموير (Disassembly & Reverse Engineering)

يوثق هذا الملف التفاصيل الهندسية الدقيقة لكفئة التعديلات التي تمت عبر الهندسة العكسية على الفيرموير الرسمي `SCO_1_V2.7.bin`, لضمان الشافية العلمية الكهملة وإتاحة إعاادة توليد الباتشات �ن الصفر (Reproducible Builds).

---

## 1. ملخص الباتشات والبصمات الرقمية (SHA-256)

| ملف الفيرموير| الوصف| البصمة التشفيرية (SHA-256) |
| :--- | :--- | :--- |
| sco_1_v2.7.bin | الف�b��موير الأصلي من الشركة (9600 Baud) | `5d6eae14db6a873e50894fddf09dde92cee9f20b61cc80fa6e75acba8f9e7936` |
| sco_1_v2.7_turbo_115200.bin | باتش السرعة التوذبو (115200 Baud - 28ms) | `62cf37309fbfb0de15703bf4fe35b5f36b556b19c3dc5b31515bbba6fa16bfc5` |
| sco_1_v2.7_turbo_waveform_115200.bin | باتش سحب عينات ADC الحقيقة الأمر 0x03 | `4489cec7bd2f170ffa776e4294d1f1f63a7a0f053a5a7237c5763eb7a8731c66` |

---

## 2. باتش التورب�و الأول: ررٹ سرعة السيريال من 9600 إلى 115200 Baud

- Firmware Flash Address: `0x800021c` (Offset `px21c`)

- Original Instruction: `movw r0, #0x2580` (Thumb-2: `42 f2 80 50`)

- Patched Instruction: `ldr.w r0, [pc, #0x84]` (Thumb-2: `df f8 84 00`)
- Literal Pool at `0x80002a4`: `1001c200` (115200 Baud)

---

## 3. باتش سحب عينات ADC الحقيقة (Waveform Streaming Patch)

- عنوان مصفوفة عينات الشاشة (Waveform Display Buffer): `0x2000ea5c` (300 points, 16-bit each)
- الكهف البرمجي الاَمن (0x801abc0 - 0x1abc0):تطبيق مخزن العتاد (HXE Buffering) لالشاشة `USART1` عننان `0x40013800`
- RX DISPATCHER Header: `0x8015414` bbranches to `CheckCommands` at `0x801ac18`
- MAIN LOOP HEADER: ` 0x8001b58` branches to `MainLoopHook` at `0x801ac60`
- ISOLATED FLAG: `0x20000080` (UNTOUCHED RAM) prevents any cross-talk with frame counters and scope settings.

---

## 4. طريقة إعاادة توليد الباتشات برمجياً: `python scripts/generate_turbo_waveform_patch.py`
