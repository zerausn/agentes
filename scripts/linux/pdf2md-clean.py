#!/usr/bin/env python3
"""
pdf2md-clean.py - Limpieza general para markdown pulido para IA
Aplica siempre: watermarks, headers repetidos, columnas, <br> tablas, guiones, concatenados
"""
import re, pathlib

# Diccionario común español para segmentar concatenados largos (headers en mayúsculas)
PALABRAS_COMUNES = ["OBJETIVO","GENERAL","MARCO","ORIGEN","PROYECTO","EVALUACION","DE","PROYECTOS",
"PROYECCION","SITUACION","ACTUAL","CON","SIN","BENEFICIOS","COSTOS","ATRIBUIBLES","AL",
"ESTUDIO","FACTIBILIDAD","TECNICA","LEGAL","ECONOMICA","GESTION","AMBIENTAL","POLITICA",
"NECESIDADES","SATISFACER","PODER","COMPRA","POSIBILIDAD","COMPRAS","TIEMPO","CONSUMO",
"ESTRATEGIA","MERCADO","LIMITACIONES","DEL","FORMULACION","Y","EL","PROCESO"]

def segmentar_mayusculas(s):
    # Para strings como "OBJETIVOGENERAL" -> "OBJETIVO GENERAL" usando diccionario
    # Greedy por palabras más largas primero
    res=[]; i=0; s_up=s.upper()
    while i < len(s_up):
        match=None
        for w in sorted(PALABRAS_COMUNES, key=len, reverse=True):
            if s_up[i:i+len(w)]==w:
                match=w; break
        if match:
            res.append(match); i+=len(match)
        else:
            # si no hay match, avanzar 1 y dejar como está (evita loop infinito)
            res.append(s_up[i]); i+=1
    # Reconstruir con espacios, pero solo si segmentamos en >1 palabra
    if len(res)>1:
        # Unir letras sueltas que no formaron palabra
        out=" ".join(res)
        # Limpiar dobles espacios de letras sueltas
        out=re.sub(r"\b ([A-Z]) \b", r" \1", out)
        return out
    return s

def limpiar(text):
    orig=text
    # 1. Watermarks
    for pat in [r"EBSCO.*?Lewis,\n?", r"EBSCOhost.*?All use subject to\n?", r"https://www\.ebsco\.com/terms-of-use\.\n?",
                r"Córdoba Padilla, M\. \(2011\).*?page=\d+ *\n?", r"Copyright © 2011.*?\n?", r"https://elibro-net.*?\n?"]:
        text=re.sub(pat,"",text,flags=re.DOTALL)
    # 2. Headers repetidos (>5 veces) se eliminan si son línea sola
    for h in ["FUNDAMENTALS OF PROJECT MANAGEMENT","AN OVERVIEW OF PROJECT MANAGEMENT",
              "FORMULACION Y EVALUACION DE PROYECTOS","FUNDAMENTALS OF PROJECT MANAGEMENT"]:
        if text.count(h)>5:
            text=re.sub(rf"^{re.escape(h)}\s*$\n?","",text,flags=re.MULTILINE)
    # 3. Número pegado "6MARCO" -> "6 MARCO", "1.6MARCO" -> "1.6 MARCO"
    text=re.sub(r"(\d+\.\d+)([A-Z])",r"\1 \2",text)
    text=re.sub(r"(\d)([A-Z]{2,})",r"\1 \2",text)
    # 4. <br> y guiones
    text=re.sub(r"(\w+)-<br>(\w+)",r"\1\2",text)
    text=re.sub(r"<br\s*/?>"," ",text)
    text=re.sub(r"(\w+)-\s*\n\s*(\w+)",r"\1\2",text)
    # 5. Concatenados largos en mayúsculas (>12 chars, sin espacio, todo mayúsculas)
    def repl_concat(m):
        s=m.group(0)
        if len(s)>=12 and s.isupper() and " " not in s:
            seg=segmentar_mayusculas(s)
            # solo si segmentó en al menos 2 palabras conocidas
            if seg.count(" ")>=1 and len(seg)>len(s):
                return seg
        return s
    text=re.sub(r"[A-Z]{12,}", repl_concat, text)
    # 6. Diccionario puntual para casos no mayúsculas (ej. Sernuevo...)
    fixes={"Sernuevoenelmercado.":"Ser nuevo en el mercado.","Adquirirnuevastecnologias,":"Adquirir nuevas tecnologias,",
           "NECESIDESA":"NECESIDADES A","PODERDECOMPRA":"PODER DE COMPRA","POSIBILIDADDECOMPRAS":"POSIBILIDAD DE COMPRAS"}
    for k,v in fixes.items():
        text=text.replace(k,v)
    text=re.sub(r",(\w)",r", \1",text)
    text=re.sub(r"\n{3,}","\n\n",text)
    text=re.sub(r"^\s*\d{1,3}\s*$\n","",text,flags=re.MULTILINE)
    return text.strip()

if __name__=="__main__":
    import sys
    for path in sys.argv[1:]:
        p=pathlib.Path(path)
        t=p.read_text(encoding="utf-8")
        c=limpiar(t)
        p.write_text(c,encoding="utf-8")
        print(f"{p.name}: {len(t)}->{len(c)} chars")
