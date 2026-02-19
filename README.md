# WEB SCRAPING BIG DATA LAB

---

## Descripcion

**WEB SCRAPING BIG DATA LAB** es un proyecto de scraping avanzado en Python, enfocado en construccion de pipelines de datos tipo lakehouse para capturar, limpiar y analizar contactos institucionales a escala.

Implementa un flujo **end-to-end**:

- Extraccion web asincrona (alta concurrencia)
- Persistencia en zona `raw` (NDJSON)
- Curacion por capas `bronze/silver/gold`
- Analitica SQL sobre SQLite (data warehouse ligero)
- KPIs de calidad y grafo de dominios (PageRank)

El sistema esta diseñado para ser:

- **Professional**: arquitectura clara por capas y artefactos reproducibles
- **Modular**: scraper, transformaciones, reportes y validacion desacoplados
- **Escalable**: crawler concurrente y esquema listo para crecer a Spark/DuckDB
- **Resiliente**: modo `auto` con fallback local para ejecucion sin internet

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WEB SCRAPING BIG DATA LAB                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Live URLs / Local Fixtures                                                 │
│           │                                                                 │
│           ▼                                                                 │
│  Async Scraper (aiohttp + bs4)                                              │
│  - crawling concurrente                                                      │
│  - extraccion emails/telefonos                                              │
│  - grafo de enlaces                                                         │
│           │                                                                 │
│           ▼                                                                 │
│  RAW ZONE (NDJSON)                                                          │
│  data/raw/pages_*.ndjson                                                    │
│  data/raw/contacts_*.ndjson                                                 │
│  data/raw/edges_*.ndjson                                                    │
│           │                                                                 │
│           ▼                                                                 │
│  Lakehouse Processor (Python + SQLite)                                      │
│  Bronze: contactos crudos                                                   │
│  Silver: emails deduplicados + score de calidad                             │
│  Gold: KPIs por dominio, institucion y grafo (PageRank)                    │
│           │                                                                 │
│           ▼                                                                 │
│  Outputs                                                                     │
│  data/lakehouse/contact_lakehouse.db                                        │
│  data/lakehouse/{bronze,silver,gold}/*.csv                                 │
│  data/outputs/metrics_report.{txt,json}                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

1. **Extract**: `apps/run_pipeline.py` ejecuta scraping asincrono desde `configs/sources.yml`.
2. **Store Raw**: páginas, contactos y enlaces se guardan en `data/raw/*.ndjson`.
3. **Transform Bronze/Silver**: `apps/transform.py` limpia y deduplica emails con reglas de calidad.
4. **Load Gold**: genera KPIs por dominio, institucion y ranking de relevancia de dominios.
5. **Report**: `apps/report.py` crea reporte final en TXT/JSON.
6. **Validate**: `apps/validate_pipeline.py` corre smoke-test end-to-end.

---

## Stack Tecnologico

| Componente | Version | Descripcion |
|------------|---------|-------------|
| Python | 3.11+ | Orquestacion del pipeline |
| aiohttp | 3.11.13 | HTTP client asincrono para crawling concurrente |
| BeautifulSoup4 | 4.13.3 | Parsing de HTML y extraccion estructurada |
| SQLite | builtin | Capa analitica SQL y persistencia gold |
| PyYAML | 6.0.2 | Configuracion de fuentes y parametros |

---

## Estructura del Proyecto

```
Web_Scraping_Correos_Instituciones_v0.0.1/
│
├── apps/
│   ├── common.py
│   ├── scraper.py
│   ├── transform.py
│   ├── report.py
│   ├── run_pipeline.py
│   └── validate_pipeline.py
│
├── configs/
│   └── sources.yml
│
├── data/
│   ├── raw/
│   ├── lakehouse/
│   │   ├── bronze/
│   │   ├── silver/
│   │   └── gold/
│   └── outputs/
│
├── fixtures/
│   └── sites/
│       ├── ministerio_educacion/
│       ├── sri/
│       └── quito_gob/
│
├── Makefile
├── requirements.txt
└── README.md
```

---

## Requisitos Previos

- Python 3.11+
- pip actualizado
- Acceso a internet opcional (modo live)

---

## Instalacion y Configuracion

### 1. Clonar el repositorio

```bash
git clone <TU_REPO_URL>
cd Web_Scraping_Correos_Instituciones_v0.0.1
```

### 2. Instalar dependencias

```bash
python -m pip install -r requirements.txt
```

### 3. Revisar fuentes de scraping

Archivo: `configs/sources.yml`

- `profiles.live`: fuentes reales
- `profiles.local`: fuentes locales de respaldo
- `settings`: profundidad, concurrencia y limites

---

## Uso del Pipeline

### Ejecucion local garantizada (sin internet)

```bash
python apps/run_pipeline.py --mode local
```

### Ejecucion automatica con fallback

```bash
python apps/run_pipeline.py --mode auto
```

### Validacion end-to-end

```bash
python apps/validate_pipeline.py
```

### Atajos Makefile

```bash
make run-local
make run-auto
make validate
```

---

## Salidas Principales

- `data/raw/pages_<run_id>.ndjson`
- `data/raw/contacts_<run_id>.ndjson`
- `data/raw/edges_<run_id>.ndjson`
- `data/lakehouse/contact_lakehouse.db`
- `data/lakehouse/bronze/contacts_<run_id>.csv`
- `data/lakehouse/silver/emails_<run_id>.csv`
- `data/lakehouse/gold/domain_kpis_<run_id>.csv`
- `data/lakehouse/gold/institution_kpis_<run_id>.csv`
- `data/lakehouse/gold/graph_kpis_<run_id>.csv`
- `data/outputs/metrics_report.txt`
- `data/outputs/metrics_report.json`

---

## Verificar que Todo Funciona

```bash
python apps/validate_pipeline.py
```

Ejemplo real validado en este repositorio:

- `pages_crawled`: 6
- `contacts_raw`: 12
- `silver_rows`: 11
- `gold_domain_rows`: 3

---

## Innovaciones Implementadas

- **Crawler asíncrono** con control de concurrencia y profundidad.
- **Arquitectura lakehouse** en capas (bronze/silver/gold).
- **Motor SQL embebido** (SQLite) para consultas analiticas reproducibles.
- **Score de calidad de contacto** por reglas de dominio institucional.
- **Analisis de grafo entre dominios** con metrica de PageRank.
- **Modo resilient/offline** para demo y testing sin dependencias externas.

---

## Desarrollo y Personalizacion

### Agregar nuevas fuentes

1. Editar `configs/sources.yml`.
2. Anadir nuevas URLs en `profiles.live`.
3. Ajustar limites de `settings` si aumentas volumen.

### Cambiar reglas de limpieza

Editar `apps/transform.py`:

- validacion de email
- deduplicacion
- `quality_score`
- clasificacion por tipo de institucion

### Ajustar estrategia de crawling

Editar `apps/scraper.py`:

- filtrado por dominio
- politicas de enlaces
- timeout/concurrencia

---

## Solucion de Problemas

### No extrae datos en modo live

1. Verificar conectividad del host.
2. Ejecutar en modo `local` para validar stack.
3. Revisar si la URL objetivo cambio estructura HTML.

### Error por dependencias

```bash
python -m pip install -r requirements.txt --upgrade
```

### Reporte vacio

1. Revisar `data/raw/*.ndjson`.
2. Ejecutar `python apps/validate_pipeline.py`.
3. Confirmar que existan emails visibles en el HTML fuente.

---

## Desarrollado por Isaac Haro

**Ingeniero en Sistemas · Full Stack · Automatizacion · Data**

- Email: zackharo1@gmail.com
- WhatsApp: 098805517
- GitHub: https://github.com/ieharo1
- Portafolio: https://ieharo1.github.io/portafolio-isaac.haro/

---

## Licencia

© 2026 Isaac Haro - Todos los derechos reservados.

---

## Acknowledgments

- [aiohttp](https://docs.aiohttp.org/)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/)
- [SQLite](https://www.sqlite.org/)
- [PyYAML](https://pyyaml.org/)
