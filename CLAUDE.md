# Comprobación de SSAA en facturas — contexto del proyecto

App local de GE&PE que revisa el concepto de servicios de ajuste (SSAA) de facturas
eléctricas: lee la factura (PDF o a mano), aplica la cláusula del contrato con los datos
de ESIOS y dice si lo facturado es correcto.

**Coste cero**: todo corre en local. Nada de Streamlit Cloud, APIs de IA ni servicios de
pago. La factura y la curva no salen del PC.

## Imagen corporativa

`estilo.py` (CSS, cabecera con logo, secciones numeradas, pie y traductor de los textos
fijos de Streamlit al español) y `.streamlit/config.toml` (tema: granate del logo #970000,
texto #1E1E1E, fondos beis, Arial; sin menú ni botón «Deploy»). Logo e icono en `assets/`
(copiados de `estudio_potencia_cuartohorario/assets`). El informe Excel usa los mismos
colores, Arial, el logo en «Resumen» y páginas ajustadas al ancho. Toda la interfaz en
español: si se añade un widget con textos propios de Streamlit, añadirlos a
`estilo.TRADUCCIONES` (solo se sustituyen textos que coinciden exactamente).

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
| `graficos.py` | Gráficos Altair en español: serie horaria/QH del índice con la media (SSAA reales) y las referencias del contrato en la leyenda, etiqueta del punto más cercano (fecha, hora y valor); barras de consumo |
| `informe.py` | Excel de revisión y fichas de contrato (`contratos_ssaa.json`, clave CUPS). Hojas: Resumen (factura, cláusula, fórmulas, líneas), «Cálculo N» por línea (parámetros + pasos con fórmula, sustitución, **fórmula viva de Excel** y valor del programa), «Detalle N» (datos horarios; en cláusulas hora a hora cada fila con su fórmula) y Diagnóstico |
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

## Cálculo paso a paso

`ssaa_motor.formula_clausula(c)` da las fórmulas en texto y `pasos_calculo(r)` los pasos
(clave, fórmula, sustitución, valor). El informe convierte cada clave en una fórmula de
Excel sobre «Detalle N» y los parámetros; verificado recalculando en Excel que coincide
con el programa en techo, banda, media ponderada e indexado cuartohorario.

## Facturas

Una factura puede traer varias líneas de SSAA de periodos distintos (Naturgy regulariza
en la factura de julio los meses de abril, mayo y junio, cada uno con su consumo). Cada
`LineaSSAA` lleva su periodo, kWh, precio €/kWh e importe y se revisa por separado.
Al añadir una factura de muestra, añadir su entrada en `facturas_ejemplo/esperado.json`.
Las pruebas que van a git usan textos sintéticos con la maqueta y cifras inventadas.

## Mecanismos soportados

Regularizaciones sobre un SSAA ya incluido en el precio (las de Endesa grandes cuentas):
- **techo**: cobertura hasta una Referencia de SSAA; cargo = MWh × (SSAA reales − ref.)
  × (1+perd) × 1,015 solo si se supera. Sin abono.
- **banda**: cargo por encima de la ref. superior y abono por debajo de la inferior.

Naturgy — regularización trimestral (banda): Σ meses n [Dif. SSAA n × (1+pérdidas) ×
Ap × Consumo n × HL]. SSAA reales = media aritmética del PFMHORAS_COM (C2_PrecioFinal)
de cada mes; la ficha dice si el contrato **indica la suma de componentes** (por defecto
Restricciones + Procesos OS + Desvíos + REER + Importe participación servicios) o **no
la especifica**. En ambos casos `comprobar_componentes()` prueba todas las combinaciones
de términos del fichero y da la referencia implícita que haría cuadrar cada línea.
Pérdidas estándar 7 % AT (6.xTD) / 17 % BT, Ap 1,02, HL 1,015. Cada mes natural se calcula
aparte (`periodo_calculo="mensual"`: una línea de varios meses se parte; consumo del mes de
la curva o prorrateado por días) y se suma por trimestre natural.
Los resultados de las facturas de muestra no se apuntan aquí (datos de clientes).
El script de descarga guarda la C2 aparte en «PFMHORAS_COM C2 mmm-aa» (no se sustituye
cuando sale la C5); si el contrato fija la C2 se lee esa pestaña, y si falta, la principal
con aviso de la liquidación que tiene.

Además: indexado (+prima), indexado con precio máximo, con mínimo y máximo, y fijo.
Agregación: media aritmética, media ponderada por consumo u hora a hora (QH si curva e
índice son QH). `importe = MWh × precio × (1+perd/100) × factor`.

Cláusulas tipo en `ssaa_motor.PLANTILLAS` (la ficha de cada CUPS guarda cuál es, el tipo
techo/banda y sus referencias; nombres antiguos en `ALIAS_PLANTILLAS`):
- «Endesa grandes cuentas — techo (PVPC)» y «— banda (PVPC)»: Total SAH del
  PVPC_DETALLE_DD, media aritmética, PERD de la tarifa del liquicomún (media aritmética) y
  1,015. Comprobado con una factura real de Endesa 6.2TD: cuadra al céntimo.
- «Endesa grandes cuentas — banda (componentes OS, C2)»: NO usa el PVPC. SSAA reales =
  media aritmética de RT3 [806] + RT6 [807] + BS3 [811] + BALX [1368] + CFP [1286] del
  Excel de componentes en liquidación C2 (copia «Componentes C2 mmm-aa»), cálculo por mes,
  mismas pérdidas y 1,015. Si la factura es anterior a la publicación de la C2, la app avisa
  de que Endesa usó una publicación anterior y debe regularizar en la factura siguiente
  (`revisar(..., fecha_emision=)`). Los meses que ya pasaron a C3+ antes de guardar la copia
  (ene–jun 2026) solo tienen la última liquidación: se avisa.

## Pendiente

- Más comercializadoras y tipologías de factura según lleguen muestras.
- Condiciones de SSAA de los contratos de las dos facturas de muestra: con variantes
  simples (SAH/SSAA ESIOS, pérdidas, 1,015) no sale una referencia constante en Naturgy.
- El 30/09/2026 del Excel de componentes (avance A2) trae valores imposibles (Total SSAA
  ~588 €/MWh, RT3 ~21.645): el motor lo avisa como anómalo.
