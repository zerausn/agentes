import sys
import logging
from datetime import datetime
from meta_uploader import upload_fb_video_standard
import schedule_jornada1_meta as sch

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

def test():
    print("=== INICIANDO PRUEBA DE BÓVEDA META ===")
    
    # Simular una entrada para Agosto de 2026 (>70 dias de distancia)
    fake_day = {"fecha": "2026-08-01"}
    
    # Asumimos que tienes un video pequeno. Usaremos una ruta dummy si es solo prueba teorica,
    # pero como Meta pide binario, no podemos hacerla completa sin un file real.
    print(f"El Agente preparara el Slot de Facebook para {fake_day['fecha']}:")
    slot = sch.build_slot_payload(fake_day["fecha"], "facebook_post")
    
    print("\n--- RESULTADO DEL SLOT CALCULADO ---")
    for key, val in slot.items():
        print(f"{key}: {val}")
        
    print("\nSi el campo 'is_draft' es True, significa que esta prueba pasara limpiamente de Facebook a la Boveda sin generar el Error #100, para luego ser graduado cuando falten 69 dias.")

if __name__ == "__main__":
    test()
