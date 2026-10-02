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
| `curva_consumo.py` | Lectura de curvas CSV/XLSX/XLS (horaria o QH). `ClienteGemweb` pendiente |
| `lectores_factura/` | `base.py`: `DatosFactura` y lector genérico (PyMuPDF + regex). Un módulo por comercializadora, registrado en `LECTORES` |
| `informe.py` | Excel de revisión y fichas de contrato (`contratos_ssaa.json`, clave CUPS) |
| `tests/test_motor.py` | `python -m unittest discover tests`. Incluye las medias reales del Total SAH abr-jun 2026 |
| `facturas_ejemplo/` | Muestras para construir los lectores |
| `revisiones_ssaa/` | Informes guardados `AAAA-MM_CUPS_nºfactura.xlsx` |

## Mecanismos soportados

Indexado (+prima), techo, suelo y techo, banda con regularización (cargo/abono; el
análisis de origen está en `..\Descarga_datos_ESIOS\ANALISIS_regularizacion_SSAA.md`,
fuera del repositorio), precio fijo.
Agregación: media aritmética, media ponderada por consumo u hora a hora (QH si curva e
índice son QH). `importe = MWh × precio × (1+perd/100) × factor`.

## Pendiente

- Lectores específicos por comercializadora, con las facturas de `facturas_ejemplo/`
  (hoy solo el genérico; todo lo leído es editable en la app).
- API de Gemweb: falta la documentación. Credencial en `GEMWEB_TOKEN` o `gemweb_token.txt`.
- El 30/09/2026 del Excel de componentes (avance A2) trae valores imposibles (Total SSAA
  ~588 €/MWh, RT3 ~21.645): el motor lo avisa como anómalo.
