import os, struct, hashlib, keystone, capstone

ORIGINAL_FW = os.path.join('firmware_tool', 'SCO_1_V2.7.bin')
OUTPUT_FW = os.path.join('firmware_tool', 'SCO_1_V2.7_TURBO_WAVEFORM_115200.bin')

ks = keystone.Ks(keystone.KS_ARCH_ARM, keystone.KS_MODE_THUMB)
cs = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)

def main():
    with open(ORIGINAL_FW, 'rb') as f:
        data = bytearray(f.read())

    # 1. Turbo Baud Rate to 115200 at 0x800021c
    data[0x21c:0x220] = bytes([0xdf, 0xf8, 0x84, 0x00]) # ldr.w r0, [pc, #0x84]
    data[0x2a4:0x2a8] = struct.pack('<I', 115200)

    # 2. Assemble Code Cave (starts at 0x801abc0)
    # Part A: SendWaveform
    code_send = '''
    .syntax unified
    .thumb

    push {r4, r5, r6, lr}
    ldr r4, =0x40013800
    ldr r5, =0x2000ea5c

    movs r1, #0xab
    bl tx_byte
    movs r1, #0xcd
    bl tx_byte
    movs r1, #0xaa
    bl tx_byte
    movs r1, #0x01
    bl tx_byte
    movs r1, #0x2c
    bl tx_byte

    movw r6, #300
    sample_loop:
    ldrh r1, [r5], #2
    usat r1, #8, r1
    bl tx_byte
    subs r6, #1
    bne sample_loop

    wait_tc_final:
    ldrh r3, [r4]
    tst r3, #0x40
    beq wait_tc_final

    pop {r4, r5, r6, pc}

    tx_byte:
    ldrh r3, [r4]
    tst r3, #0x80
    beq tx_byte
    strh r1, [r4, #4]
    bx lr

    .pool
    '''
    enc_send, _ = ks.asm(code_send, 0x801abc0)
    while len(enc_send) % 4 != 0:
        enc_send.append(0)

    addr_check = 0x801abc0 + len(enc_send)

    # Part B: CheckCommands
    code_check = '''
    .syntax unified
    .thumb

    ldr r1, =0x2000035c
    ldrb r0, [r1]
    ldrb r2, [r1, #1]

    cmp r0, #2
    beq is_cmd2
    cmp r2, #2
    beq is_cmd2

    cmp r0, #3
    beq is_cmd3
    cmp r2, #3
    beq is_cmd3

    b finish_rx

    is_cmd2:
    movs r0, #1
    ldr r2, =0x20000049
    strb r0, [r2]
    b clear_rx_and_finish

    is_cmd3:
    movs r0, #1
    ldr r2, =0x20000080
    strb r0, [r2]
    b clear_rx_and_finish

    clear_rx_and_finish:
    movs r0, #0
    strb r0, [r1]
    strb r0, [r1, #1]

    finish_rx:
    movs r0, #0
    ldr r1, =0x20000360
    strh r0, [r1]
    pop {r4, pc}

    .pool
    '''
    enc_check, _ = ks.asm(code_check, addr_check)
    while len(enc_check) % 4 != 0:
        enc_check.append(0)

    addr_hook = addr_check + len(enc_check)

    # Part C: MainLoopHook
    code_hook = f'''
    .syntax unified
    .thumb

    ldr r0, =0x20000080
    ldrb r1, [r0]
    cbz r1, skip_waveform

    movs r1, #0
    strb r1, [r0]

    bl 0x801abc0

    skip_waveform:
    add sp, #0x3c
    pop.w {{r4, r5, r6, r7, r8, sb, sl, fp, pc}}

    .pool
    '''
    enc_hook, _ = ks.asm(code_hook, addr_hook)
    while len(enc_hook) % 4 != 0:
        enc_hook.append(0)

    cave_bytes = bytes(enc_send + enc_check + enc_hook)
    cave_offset = 0x1abc0
    data[cave_offset:cave_offset+len(cave_bytes)] = cave_bytes

    # 3. Hook in RX Dispatcher at 0x8015414
    enc_rx_jump, _ = ks.asm(f'.syntax unified\n.thumb\nb.w {hex(addr_check)}', 0x8015414)
    data[0x15414:0x15418] = bytes(enc_rx_jump)
    # Pad remaining bytes of old cmd2 check with NOPs up to 0x8015438
    for p in range(0x15418, 0x15438, 2):
        data[p:p+2] = bytes([0x00, 0xbf])

    # 4. Hook in Main Loop at 0x8001b58
    enc_main_jump, _ = ks.asm(f'.syntax unified\n.thumb\nb.w {hex(addr_hook)}\nnop', 0x8001b58)
    data[0x1b58:0x1b58+len(enc_main_jump)] = bytes(enc_main_jump)

    with open(OUTPUT_FW, 'wb') as f:
        f.write(data)

    sha = hashlib.sha256(data).hexdigest()
    print(f'[SUCCESS] Generated {OUTPUT_FW} (SHA256: {sha})')

if __name__ == '__main__':
    main()

