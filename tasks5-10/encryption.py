from collections import Counter

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZäöüÄÖÜß0123456789 .,!?;:-_()"


def encrypt(text, key ,mult):
    encrypted_text = ""
    for pos, char in enumerate(text):
        if char in ALPHABET:
            old_index = ALPHABET.index(char)
            pos_shift = (key+pos*mult) % len(ALPHABET)
            new_index = (old_index+pos_shift) % len(ALPHABET)
            encrypted_text += ALPHABET[new_index]
        else:
            encrypted_text += char #wird nicht verschlüsselt
    return encrypted_text

def decrypt(text, key, mult):
    decrypted_text = ""
    for pos, char in enumerate(text):
        if char in ALPHABET:
            old_index = ALPHABET.index(char)
            pos_shift = (key+pos*mult) % len(ALPHABET)
            new_index = (old_index-pos_shift) % len(ALPHABET)
            decrypted_text += ALPHABET[new_index]
        else:
            decrypted_text += char
    return decrypted_text

#Häufigkeitsanalyse: Bringt nicht viel, da Verschiebung von Zeichenposition abhängig ist 
def frequency_analysis(ciphertext):
    frequencies = Counter(ciphertext)

    print("\nFrequenzanalyse des Geheimtexts:")
    for char, count in frequencies.most_common(10):
        print(f"'{char}': {count}-mal")

#Mögl Bruteforce: ALPHABET*ALPHABET, in diesem Fall 80*80 = 6400 Möglichkeiten
def brute_force(text):
    for possible_mult in range(len(ALPHABET)):
        for possible_key in range(len(ALPHABET)):
            guess = decrypt(text, possible_key, possible_mult)
            print(f"Key {possible_key}, MULT {possible_mult}: {guess}")


text = "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed diam nonumy eirmod tempor invidunt ut labore et dolore magna aliquyam erat, sed diam voluptua."
ciphertext = encrypt(text,15,5)

print("Klartext:\n"+text)
print("Verschlüsselt:\n"+ciphertext)
print("Falsch entschlüsselt:\n"+decrypt(ciphertext,14,5))
print("Korrekt entschlüsselt:\n"+decrypt(ciphertext,15,5))

frequency_analysis(ciphertext)
#brute_force(ciphertext)



