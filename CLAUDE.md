# Comprobación de SSAA en facturas — contexto del proyecto

App local de GE&PE que revisa el concepto de servicios de ajuste (SSAA) de facturas
eléctricas: lee la factura (PDF o a mano), aplica la cláusula del contrato con los datos
de ESIOS y dice si lo facturado es correcto.

**Coste cero**: todo corre en local. Nada de Streamlit Cloud, APIs de IA ni servicios de
pago. La factura y la curva no salen del PC.

## Datos

Lee, sin modificarlos, los Excel históricos del proyecto hermano
`..\Descarga_datos_ESIOS` (ruta en `config.CARPETA_ESIOS`, variable `SSAA_CARPETA_ESIOS`):
`AAAA_Historico_PVPC_horario.xlsx` (Total SAH, PERD PVPC) y
`AAAA_Historico_componentes_ESIOS.xlsx` (SSAA QH por componente, `Pérdidas mmm-aa`,
`Pérdidas QH mmm-aa`). Se compara siempre con el último dato publicado que haya en ellos.
Para actualizarlos se usan los scripts de aquel proyecto, no se duplica la descarga.

Claves internas con la convención ESIOS: `(fecha, hora 1..25)` y `(fecha, hora, cuarto)`;
así los días de cambio de hora no necesitan zona horaria.

## Ficheros

| Fichero | Qué hace |
|---|---|
| `app_revision_ssaa.py` | Interfaz Streamlit: `streamlit run app_revision_ssaa.py` → localhost:8501 |
| `ssaa_motor.py` | Cálculo: `Contrato` (índice, agregación, mecanismo, pérdidas, factor), `revisar()`, `diagnostico()` |
| `ssaa_datos_esios.py` | Lectura de los Excel de ESIOS a series |
| `curva_consumo.py` | Lectura de curvas CSV/XLSX/XLS (horaria o QH) y reparto de los días de cambio de hora |
| `gemweb.py` | API de Gemweb (adaptado de `estudio_potencia_cuartohorario/potencia/gemweb.py`): CUPS → id, curva cuartohoraria |
| `lectores_factura/` | `base.py`: `DatosFactura`, `LineaSSAA` y lector genérico (PyMuPDF + regex). Lectores `endesa.py` y `naturgy.py` (grandes cuentas), elegidos por CIF de la comercializadora y registrados en `LECTORES` |
| `informe.py` | Excel de revisión y fichas de contrato (`contratos_ssaa.json`, clave CUPS) |
| `tests/` | `python -m unittest discover tests`. Incluye las medias reales del Total SAH abr-jun 2026 y una API de Gemweb simulada |
| `facturas_ejemplo/` | Facturas reales de muestra y `esperado.json` con lo que debe leer cada una (fuera de git; lo usa `tests/test_lectores.py`) |
| `revisiones_ssaa/` | Informes guardados `AAAA-MM_CUPS_nºfactura.xlsx` |

## Gemweb

`https://api.gemweb.es`, XML. Fechas con la hora de FIN del cuarto y siempre 96 cuartos
por día: en marzo lo de las 02:xx se suma a la hora 3 de ESIOS y en octubre se reparte a
medias entre las horas 3 y 4 (`curva_consumo.curva_reloj_a_esios`).

Credenciales, nunca en el repositorio, por este orden: variables `GEMWEB_CLIENT_ID` /
`GEMWEB_CLIENT_SECRET`; `%APPDATA%\ValidadorSSAA\gemweb.json` (guardadas desde la app,
cifradas con DPAPI); `%APPDATA%\EstudioPotencia\gemweb.json`;
`..\API_Gemweb\.streamlit\secrets.toml`.

## GitHub

`origin` = github.com/iyadazig/validador_SSAA_facturas. Se sube cada commit. **Nunca**
datos de clientes (facturas, curvas, CUPS reales, condiciones de contrato, informes) ni
credenciales: están en `.gitignore`. Las pruebas usan CUPS ficticios y bandas genéricas.

## Facturas

Una factura puede traer varias líneas de SSAA de periodos distintos (Naturgy regulariza
en la factura de julio los meses de abril, mayo y junio, cada uno con su consumo). Cada
`LineaSSAA` lleva su periodo, kWh, precio €/kWh e importe y se revisa por separado.
Al añadir una factura de muestra, añadir su entrada en `facturas_ejemplo/esperado.json`.
Las pruebas que van a git usan textos sintéticos con la maqueta y cifras inventadas.

## Mecanismos soportados

Indexado (+prima), techo, suelo y techo, banda con regularización (cargo/abono; el
análisis de origen está en `..\Descarga_datos_ESIOS\ANALISIS_regularizacion_SSAA.md`,
fuera del repositorio), precio fijo.
Agregación: media aritmética, media ponderada por consumo u hora a hora (QH si curva e
índice son QH). `importe = MWh × precio × (1+perd/100) × factor`.

## Pendiente

- Más comercializadoras y tipologías de factura según lleguen muestras.
- Condiciones de SSAA de los contratos de las dos facturas de muestra: con variantes
  simples (SAH/SSAA ESIOS, pérdidas, 1,015) no sale una referencia constante en Naturgy.
- El 30/09/2026 del Excel de componentes (avance A2) trae valores imposibles (Total SSAA
  ~588 €/MWh, RT3 ~21.645): el motor lo avisa como anómalo.
