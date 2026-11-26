import hashlib as hl
texto = "Senha"

print(hl.sha256(texto.encode('utf-8')).hexdigest())
