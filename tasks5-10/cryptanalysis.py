UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWERCASE = "abcdefghijklmnopqrstuvwxyz"

def decrypt_caesar(text, shift):
    decrypted = ""
    for char in text:
        if char in UPPERCASE:
            old_index = UPPERCASE.index(char)
            new_index = (old_index + shift) % 26
            decrypted += UPPERCASE[new_index]

        elif char in LOWERCASE:
            old_index = LOWERCASE.index(char)
            new_index = (old_index + shift) % 26
            decrypted += LOWERCASE[new_index]
        else:
            decrypted += char
    return decrypted

def brute_force(text):
    for i in range(1,26):
        plaintext = decrypt_caesar(text,i)
        print(f"{i}: {plaintext}")
        
example = "Bcgvzvrera Fvr Vuer Qngra zvg Qngn Ratvarrevat"
brute_force(example)
