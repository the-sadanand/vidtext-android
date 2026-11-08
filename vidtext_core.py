"""Core logic for VidText (no UI). Same file format as the desktop app (VT2)."""
import hashlib
import os
import random
import struct
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt

MAGIC = b"VT2"
MARKER = "=== appendix ==="
MAX_BYTES = 40 * 1024 * 1024  # phones run out of memory on bigger files

SYLLABLES = [c + v for c in "kmrt" for v in "aeio"]
HEX = "0123456789abcdef"
ENC_TABLE = {ord(h): s for h, s in zip(HEX, SYLLABLES)}

COVER_TOPICS = {
    "Notes on Photosynthesis": "Photosynthesis lets plants turn sunlight, water and carbon dioxide "
        "into glucose and oxygen. These notes summarise the light-dependent reactions and the Calvin cycle.",
    "A Short History of the Printing Press": "Movable type changed how knowledge spread across Europe. "
        "This document outlines the key inventors, materials and social effects of early printing.",
    "Basics of Urban Beekeeping": "Keeping bees in cities is growing in popularity. "
        "These notes cover hive placement, seasonal care and local regulations.",
    "Overview of the Water Cycle": "Water moves between oceans, atmosphere and land through evaporation, "
        "condensation and precipitation. This summary explains each stage briefly.",
    "Introduction to Chess Openings": "Good openings control the centre and develop pieces quickly. "
        "Below are common principles and a few classic lines worth memorising.",
    "Understanding Compound Interest": "Compound interest earns returns on both the original amount and "
        "previously earned interest. These notes walk through the formula with simple examples.",
}


def _key(code_word, salt):
    return scrypt(code_word.encode("utf-8"), salt, 32, N=2 ** 15, r=8, p=1)


def encrypt_video(video_path, code_word):
    name = video_path.name.encode("utf-8")
    plain = struct.pack(">H", len(name)) + name + video_path.read_bytes()
    salt, nonce = os.urandom(16), os.urandom(12)
    ct, tag = AES.new(_key(code_word, salt), AES.MODE_GCM, nonce=nonce).encrypt_and_digest(plain)
    return MAGIC + salt + nonce + ct + tag  # tag last = same layout as the desktop app


def decrypt_blob(blob, code_word):
    if blob[:3] != MAGIC:
        raise ValueError("This text file does not contain hidden data.")
    salt, nonce, rest = blob[3:19], blob[19:31], blob[31:]
    ct, tag = rest[:-16], rest[-16:]
    try:
        plain = AES.new(_key(code_word, salt), AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ct, tag)
    except ValueError:
        raise ValueError("Wrong code word (or the text was edited).")
    (n,) = struct.unpack(">H", plain[:2])
    return plain[2:2 + n].decode("utf-8"), plain[2 + n:]


def bytes_to_syllables(data):
    hx = (struct.pack(">Q", len(data)) + data).hex()
    hx += "0" * (-len(hx) % 3)
    return hx.translate(ENC_TABLE)


def syllables_to_bytes(text):
    for h, s in zip(HEX, SYLLABLES):
        text = text.replace(s, h)
    if len(text) < 16 or any(c not in HEX for c in text[:64]):
        raise ValueError("Text is damaged or incomplete.")
    raw = bytes.fromhex(text[: len(text) - len(text) % 2])
    (length,) = struct.unpack(">Q", raw[:8])
    if 8 + length > len(raw):
        raise ValueError("Text is damaged or incomplete.")
    return raw[8:8 + length]


def write_text_document(blob, out_path):
    syl = bytes_to_syllables(blob)
    title, intro = random.choice(list(COVER_TOPICS.items()))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"{title}\n{'=' * len(title)}\n\n{intro}\n\n{MARKER}\n")
        for i in range(0, len(syl), 72):
            line = syl[i:i + 72]
            f.write(" ".join(line[j:j + 6] for j in range(0, len(line), 6)) + "\n")


def read_blob(txt_path):
    text = Path(txt_path).read_text(encoding="utf-8")
    if MARKER not in text:
        raise ValueError("This is not a file made by VidText.")
    return syllables_to_bytes("".join(text.split(MARKER, 1)[1].split()))


def hide_video(video_path, out_path, code_word, say):
    video_path, out_path = Path(video_path), Path(out_path)
    if not video_path.is_file():
        raise ValueError("Choose a video first.")
    if not code_word:
        raise ValueError("Enter a code word.")
    if video_path.stat().st_size > MAX_BYTES:
        raise ValueError("Video is over 40 MB. Use the laptop app for big videos.")
    say("Encrypting video...")
    blob = encrypt_video(video_path, code_word)
    say("Writing text document...")
    write_text_document(blob, out_path)
    del blob
    say("Verifying the text restores the exact video...")
    _, restored = decrypt_blob(read_blob(out_path), code_word)
    if hashlib.sha256(restored).digest() != hashlib.sha256(video_path.read_bytes()).digest():
        raise RuntimeError("Verification failed. Nothing was deleted.")
    return out_path


def reveal_video(txt_path, out_dir, code_word, say):
    if not Path(txt_path).is_file():
        raise ValueError("Choose the text file first.")
    if not code_word:
        raise ValueError("Enter the code word.")
    say("Reading text and decrypting...")
    name, video = decrypt_blob(read_blob(txt_path), code_word)
    out = Path(out_dir) / Path(name).name
    say("Saving video...")
    out.write_bytes(video)
    return out
