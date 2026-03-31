# Propuesta: Sistema de Agentes Coordinados Mejorado

**Fecha:** 31 de marzo de 2026  
**Versión:** 1.0  
**Estado:** Para revisar y mejorar

---

## 1. Análisis de la Propuesta Original

La propuesta original define un agente (Claude Code) con responsabilidades bien claras:
- 📝 Documentar todo
- 🎨 Colaborar en diseño
- 🚀 Subir código a GitHub
- ✅ Verificar fallos
- 📊 Actualizar historial

**Fortalezas:**
- Responsabilidades claras
- Enfoque en documentación
- Integración con Git

**Debilidades identificadas:**
- Sin mecanismo de coordinación entre agentes
- Sin versionado de decisiones
- Sin feedback loop automático
- Sin control de calidad antes de commits
- Sin registro de auditoría

---

## 2. Propuesta Mejorada: Arquitectura Multi-Agente

### 2.1 Estructura de Carpetas Recomendada

```
antigravity/
├── agentes/
│   ├── PROPUESTA_SISTEMA_AGENTES_COORDINADOS.md (este archivo)
│   ├── configs/
│   │   ├── agente-coordinador.yaml
│   │   ├── agente-documentador.yaml
│   │   ├── agente-revisor.yaml
│   │   ├── agente-qa.yaml
│   │   └── agente-github.yaml
│   ├── scripts/
│   │   ├── init-agents.ps1
│   │   ├── health-check.ps1
│   │   └── ci-pipeline.ps1
│   └── historial/
│       ├── sesiones/
│       ├── decisiones/
│       └── ejecuciones/
├── proyectos/
├── docs/
└── ...otros directorios
```

### 2.2 Rol de Cada Agente

#### **Agente 1: COORDINADOR** ⚙️
- **Función Principal:** Orquestar el flujo de trabajo
- **Responsabilidades:**
  - Recibir peticiones del usuario
  - Asignar tareas a otros agentes
  - Monitorear estado de ejecución
  - Resolver conflictos entre agentes
  - Generar reportes de progreso
- **Entrada:** Peticiones del usuario
- **Salida:** Plan de acción distribuido

#### **Agente 2: DOCUMENTADOR** 📝
- **Función Principal:** Documentar todo el proceso
- **Responsabilidades:**
  - Generar documentación de código
  - Mantener historial de conversaciones
  - Crear registros de decisiones arquitectónicas
  - Documentar APIs y funciones
  - Mantener changelog
- **Entrada:** Cambios de código, decisiones
- **Salida:** Archivos markdown, historial.md

#### **Agente 3: REVISOR** 🔍
- **Función Principal:** Revisar calidad de código antes de commit
- **Responsabilidades:**
  - Analizar código generado
  - Verificar adherencia a estándares
  - Revisar lógica y seguridad
  - Sugerir mejoras
  - Aprobar o rechazar cambios
- **Entrada:** Código generado
- **Salida:** Reporte de revisión

#### **Agente 4: QA/PRUEBAS** ✅
- **Función Principal:** Garantizar calidad
- **Responsabilidades:**
  - Ejecutar pruebas unitarias
  - Verificar fallos críticos
  - Testear funcionalidad completa
  - Generar reportes de cobertura
  - Validar contra especificaciones
- **Entrada:** Código revisado
- **Salida:** Reporte de tests

#### **Agente 5: GITHUB/GIT** 🚀
- **Función Principal:** Gestionar versionado
- **Responsabilidades:**
  - Crear branches feature
  - Hacer commits con mensajes estándar
  - Crear pull requests
  - Autorizar merges a main
  - Generar releases
  - Actualizar tags de versión
- **Entrada:** Código aprobado + descripción
- **Salida:** Repositorio actualizado

### 2.3 Flujo de Ejecución Propuesto

```
USUARIO
   ↓
COORDINADOR [Recibe petición]
   ├→ DOCUMENTADOR [Genera especificación]
   ├→ DISEÑADOR [Propone arquitectura]
   ├→ DESARROLLADOR [Genera código]
   │   ├→ REVISOR [Valida código]
   │   │   ├→ ¿APROBADO? → SÍ ↓ / NO → volver a DESARROLLADOR
   │   ├→ QA [Ejecuta tests]
   │   │   ├→ ¿PASA? → SÍ ↓ / NO → volver a DESARROLLADOR
   │   └→ DOCUMENTADOR [Documenta cambios]
   └→ GITHUB [Sube a repositorio]
   ↓
USUARIO [Confirmación de éxito]
```

---

## 3. Sistema de Comunicación Inter-Agentes

### 3.1 Archivo de Estado Compartido
**Ubicación:** `antigravity/agentes/historial/estado-actual.json`

```json
{
  "sesion_id": "2026-03-31-001",
  "peticion_usuario": "Crear función de login",
  "estado": "en_progreso",
  "agentes": {
    "coordinador": {"status": "activo", "timestamp": "2026-03-31T10:00:00Z"},
    "desarrollador": {"status": "generando_código", "progreso": 45},
    "revisor": {"status": "en_espera", "timestamp": null},
    "qa": {"status": "en_espera", "timestamp": null},
    "github": {"status": "en_espera", "timestamp": null}
  },
  "ramas_activas": ["feature/login"],
  "historial_decisiones": [...]
}
```

### 3.2 Protocolo de Mensajes
Cada agente registra acciones en:
- **Logs:** `agentes/historial/logs/YYYYMMDD-agente.log`
- **Decisiones:** `agentes/historial/decisiones/YYYYMMDD.md`
- **Sesiones:** `agentes/historial/sesiones/sesion-{id}.md`

---

## 4. Control de Versión y Auditoría

### 4.1 Archivo de Historial Mejorado
**Ubicación:** `Historial de Conversaciones y Sesiones de Desarrollo.md`

```markdown
# Sesión: 2026-03-31-001
- **Fecha:** 31-03-2026 10:00 UTC
- **Petición:** Crear función de login
- **Iniciador:** Usuario (zerausn)

## Decisiones Arquitectónicas
1. Usar JWT para autenticación
2. Hash con bcrypt para contraseñas
3. Base de datos: PostgreSQL

## Agentes Involucrados
- Coordinador: Orquestación ✅
- Desarrollador: Codificación ✅
- Revisor: Code review ✅
- QA: Tests 🟡 (En progreso)
- GitHub: Deploy ⏳ (En espera)

## Cambios Generados
- `src/auth/login.ts` (nuevo)
- `tests/auth.test.ts` (nuevo)

## Estado Final
✅ COMPLETADO - Mergueado a main
```

---

## 5. Mejoras Específicas Propuestas

### 5.1 Antes (Sistema Original)
```
Claude Code recibe petición
    ↓
Programa todo
    ↓
Intenta subir a GitHub
    ↓
(Posible fallo - sin validación previa)
```

### 5.2 Después (Sistema Mejorado)
```
Coordinador recibe petición
    ↓
Documentador planifica
    ↓
Desarrollador codifica
    ↓
Revisor valida (QA)
    ↓
QA ejecuta tests
    ↓
Documentador registra
    ↓
GitHub sube cambios
    ↓
Coordinador confirma éxito
```

### 5.3 Checklist de Calidad Antes de Commit

```yaml
# agentes/configs/qa-checklist.yaml
antes_de_commit:
  - codigo_compila: true
  - tests_pasan: true
  - cobertura_minima: 80
  - sin_errores_linting: true
  - seguridad_validada: true
  - documentacion_actualizada: true
  - mensaje_commit_formato: "feat|fix|docs|style|refactor: descripción"
  - rama_correcta: "feature/*"
```

---

## 6. Implementación Recomendada

### Fase 1: Configuración (Semana 1)
- [ ] Crear estructura de carpetas
- [ ] Definir archivos de configuración YAML
- [ ] Implementar sistema de logging
- [ ] Crear archivo de estado compartido

### Fase 2: Agentes Básicos (Semana 2-3)
- [ ] Agente Coordinador
- [ ] Agente GitHub/Git
- [ ] Agente Documentador

### Fase 3: Agentes Avanzados (Semana 4-5)
- [ ] Agente Revisor
- [ ] Agente QA
- [ ] Sistema de feedback loop

### Fase 4: Automatización (Semana 6)
- [ ] Scripts PowerShell para automatización
- [ ] CI/CD pipeline
- [ ] Monitoreo de agentes

---

## 7. Preguntas para Mejora

**Puntos que necesitan revisión:**

1. ¿Cómo manejar conflictos entre agentes?
2. ¿Cuál es la frecuencia ideal de ejecución?
3. ¿Qué límites de recursos usar por agente?
4. ¿Cómo escalar esto a múltiples proyectos?
5. ¿Hay dependencias entre repositorios que deba considerar?
6. ¿Qué nivel de autonomía debe tener cada agente?
7. ¿Cómo integrar con problemas/issues de GitHub?
8. ¿Quién aprueba merges a `main`? (Control de acceso)

---

## 8. Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|--------|-----------|
| Agentes en deadlock | Media | Alto | Timeout + reinicio automático |
| Múltiples commits simultáneos | Alta | Medio | Control de mutex en Git |
| Documentación desincronizada | Media | Medio | Validación automática |
| Pérdida de contexto entre sesiones | Baja | Alto | Persistencia en estado.json |
| Agente QA muy estricto | Media | Bajo | Umbrales configurables |

---

## 9. Referencias y Recursos

- **Git Workflow:** [GitHub Flow](https://guides.github.com/introduction/flow/)
- **Semantic Versioning:** [semver.org](https://semver.org/lang/es/)
- **Conventional Commits:** [conventionalcommits.org](https://www.conventionalcommits.org/)

---

**PRÓXIMO PASO:** Un agente revisor debe analizar esta propuesta y señalar:
- ¿Qué está bien?
- ¿Qué está mal?
- ¿Qué falta?
- ¿Qué se puede simplificar?
