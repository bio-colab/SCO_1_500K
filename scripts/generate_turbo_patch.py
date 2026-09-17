import os, struct, hashlib

ORIGINAL_FW = os.path.join("firmware_tool", "SCO_1_V2.7.bin")
PATCHED_FW = os.path.join("firmware_tool", "SCO_1_V2.7_TURBO_115200.bin")

def generate_patch():
    with open(ORIGINAL_FW, "rb") as f:
        data = bytearray(f.read())
    print("[INFO] Original size:", len(data))
    assert data[0x21c:0x220] == bytes([0x4f, 0xf4, 0x16, 0x50])
    data[0x21c:0x220] = bytes([0xdf, 0xf8, 0x84, 0x00])
    data[0x2a4:0x2a8] = struct.pack("<I", 115200)
    with open(PATCHED_FW, "wb") as f:
        f.write(data)
    print("[SUCCESS] Generated:", PATCHED_FW)

if __name__ == "__main__":
    generate_patch()
