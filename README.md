# API CIE-10 · Catálogo general

API que sirve **todo el catálogo CIE-10** (12,424 códigos), organizado por
los 22 capítulos oficiales, con búsqueda por texto y paginación. Los datos
viven en **MongoDB**.

## Archivos

```
maternal_api/
├── main.py                # API FastAPI (lee/escribe en MongoDB)
├── requirements.txt
├── Dockerfile              # build usado por Coolify para desplegar
├── scripts/
│   └── build_seed.py      # genera data/cie10_full.json a partir de un CSV crudo
├── data/
│   └── cie10_full.json    # catálogo semilla, con capítulo y UUID ya calculados
└── README.md
```

## Base de datos

Los datos viven en la colección `MONGO_COLLECTION` (default `codes`) de la
base `MONGO_DB` (default `cie10`). Si la colección está vacía, la API la
puebla automáticamente al arrancar desde `data/cie10_full.json`, así que no
hace falta correr ningún script aparte en un despliegue normal.

Variables de entorno (todas opcionales, con default para desarrollo local):

| Variable | Default | Descripción |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | Cadena de conexión a MongoDB |
| `MONGO_DB` | `cie10` | Nombre de la base de datos |
| `MONGO_COLLECTION` | `codes` | Nombre de la colección |

### El campo `id`

`id` es un **UUID** (no un entero secuencial), generado de forma
determinística a partir del `code` (UUID5). Si el CSV se regenera desde la
fuente original, cada código conserva siempre el mismo UUID — no se rompen
referencias que otros sistemas ya guarden con ese id como llave foránea.

### Regenerar la semilla desde un CSV nuevo

Si el catálogo cambia (nuevo CSV con columnas `id,code,description,...`):

```bash
# 1. Copia el CSV a data/cie10_full.csv
# 2. Regenera el JSON (recalcula el capítulo y el UUID de cada código)
python scripts/build_seed.py
# 3. Borra la colección en MongoDB para que se vuelva a poblar en el próximo arranque
```

## Cómo correrla localmente

1. Levanta un MongoDB local (si no tienes uno corriendo ya):

```bash
docker run -d --name cie10-mongo-local -p 27017:27017 mongo:4.4
```

Se usa `mongo:4.4` (no una versión más nueva) porque es la misma que corre
en producción — ver la nota de compatibilidad en la sección de Coolify.

2. Instala dependencias y arranca la API:

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Luego abre `http://127.0.0.1:8000/docs` para la documentación interactiva (Swagger UI).

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/` | Info general de la API |
| GET | `/chapters` | Lista de los 22 capítulos CIE-10 (para el desplegable) |
| GET | `/codes` | Lista paginada, con filtros `?q=`, `?chapter=`, `?limit=`, `?offset=` |
| GET | `/codes/{code}` | Detalle de un código puntual, ej `/codes/J189` |

`/codes` devuelve un máximo de 20 resultados por página, porque el catálogo
completo tiene ~12,400 registros y no conviene traerlos todos de una sola
vez al frontend.

```bash
# Capítulos disponibles
curl http://127.0.0.1:8000/chapters

# Códigos del capítulo "Embarazo, parto y puerperio", página 1
curl "http://127.0.0.1:8000/codes?chapter=Embarazo,%20parto%20y%20puerperio&limit=20&offset=0"

# Buscar por texto libre en cualquier capítulo
curl "http://127.0.0.1:8000/codes?q=neumonia"

# Siguiente página
curl "http://127.0.0.1:8000/codes?q=neumonia&limit=20&offset=20"

# Detalle de un código puntual
curl http://127.0.0.1:8000/codes/J189
```

## Idea de integración en el frontend

1. **Pantalla general de búsqueda de códigos CIE-10**:
   - Desplegable de **capítulos** (`GET /chapters`).
   - Al elegir un capítulo, listar sus códigos con `GET /codes?chapter=...`
     paginado (botón "cargar más" usando `offset`).
   - Un buscador libre (`GET /codes?q=...`) con debounce, para cuando el
     usuario ya conoce parte del código o la descripción, sin necesidad de
     navegar por capítulo.
2. El `id` (UUID) de cada registro es estable entre despliegues, útil para
   relacionar con otras tablas que ya usen ese id como llave foránea.

## Producción

URL actual: `http://61ymibxfmomlho8gavsxanyd.161.132.37.215.sslip.io/`
(Swagger en `/docs`).

Corre en el servidor `srv-215-wireguard` de Coolify (proyecto `HRLoreto` →
`production`). Se movió ahí desde `srv-137` para liberar espacio en ese
servidor, clonando los recursos (`cat_gen_cie10_api` y `cie10-mongo-db`) y
apuntando el `MONGO_URI` de la app a la cadena de conexión interna del
Mongo clonado.

Pendiente: los recursos en Coolify quedaron con el nombre de clon
(`clone-of-cat_gen_cie10_api`, `cie10-mongo-db-clone-...`) — conviene
renombrarlos (quitar el prefijo/sufijo "clone") una vez que se confirme que
nadie sigue usando la URL vieja del `.137`, y entonces sí dar de baja los
recursos originales en `srv-137`.

## Desplegar en Coolify

1. **Crea el recurso de MongoDB** en el mismo proyecto de Coolify (igual que
   la base MySQL que ya tienes ahí): *New resource → Database → MongoDB*.
   Coolify te da una cadena de conexión interna una vez que arranca (algo
   como `mongodb://root:password@nombre-del-servicio:27017/?directConnection=true`).

   > **Compatibilidad de CPU**: MongoDB 5.0+ requiere que el servidor
   > tenga soporte de instrucciones **AVX**. Si el servidor no lo tiene
   > (común en VPS económicos), el contenedor crashea en bucle con
   > `Illegal instruction (core dumped)`. En ese caso, cambia la imagen a
   > una versión ≤ 4.4 en *General → Container image* (campo de la imagen,
   > donde por defecto dice `mongo:7`) y reinicia el recurso.

2. **La app** despliega con **Build Pack: Dockerfile** (ya está en la raíz
   del repo) y **Port: 8000**. En *Settings → Environment Variables*
   agrega:
   - `MONGO_URI` = la cadena de conexión interna del paso 1
   - `MONGO_DB` = `cie10` (o el nombre que prefieras)
   - `MONGO_COLLECTION` = `codes`
3. **Redeploy** la app. En el primer arranque, si la colección está vacía,
   se puebla sola desde `data/cie10_full.json` — no hace falta ejecutar nada
   manualmente en el servidor.
4. Verifica con `curl https://<dominio-en-coolify>/chapters` que responda
   los 22 capítulos.

### Vaciar/re-sembrar la colección en producción

Si cambias la semilla (`data/cie10_full.json`) y necesitas que producción
la vuelva a cargar, hay que vaciar la colección manualmente — la API solo
siembra si está vacía.

1. En el recurso `cie10-mongo-db` en Coolify → **Terminal**.
2. La imagen `mongo:4.4` trae el cliente clásico `mongo` (no `mongosh`).
   Autentícate con el usuario `root` y la contraseña de la cadena de
   conexión interna:
   ```
   mongo cie10 -u root -p 'TU_PASSWORD' --authenticationDatabase admin --eval "db.codes.drop()"
   ```
   (ajusta `cie10` y `codes` si usaste otros nombres en `MONGO_DB` /
   `MONGO_COLLECTION`)
3. **Redeploy/Restart** la app para que la vuelva a poblar.

## Siguientes pasos sugeridos

- Agregar autenticación (API key o JWT) antes de exponerla en producción.
- El CORS está abierto (`allow_origins=["*"]`) en `main.py`; si el frontend
  ya tiene un dominio fijo, conviene restringirlo a ese dominio.
- Si necesitas una vista especializada (ej. un subconjunto de códigos para
  un caso de uso puntual), se puede agregar un endpoint que filtre por
  prefijos de código sobre la misma colección, sin duplicar datos.
