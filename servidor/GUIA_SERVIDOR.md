# Revisor de SSAA — instalación en el servidor

Guía para dejar la aplicación de revisión de servicios de ajuste (SSAA) funcionando en un
servidor de la oficina, de forma que los 9 compañeros la usen desde el navegador, en la
oficina o por VPN, sin instalar nada en sus ordenadores.

```
 Oficina (red local)            Teletrabajo (VPN)
  navegador ──┐                  navegador ──┐
              ├──  http://SERVIDOR:8501  ────┤
         ┌────┴──────────────────────────────┴────┐
         │ Servidor (siempre encendido)           │
         │  · App (Python + Streamlit)            │
         │  · Base de datos revisor_ssaa.db       │
         │    (usuarios, fichas, historial)       │
         │  · Excel de ESIOS y sus descargas      │
         │  · Credenciales de ESIOS y Gemweb      │
         └────────────────────────────────────────┘
```

Coste: ninguno. Todo es software libre (Python, Streamlit, SQLite) y corre en el servidor.

## 1. Requisitos

- Windows (servidor o PC) **siempre encendido**, en la red de la oficina.
- **Python 3.11 o posterior** (desarrollado con 3.13), instalado para todos los usuarios.
- Unos 2 GB libres de disco.
- Salida a internet hacia `api.esios.ree.es` (datos de REE) y `api.gemweb.es` (curvas).
- Una **cuenta de Windows para el servicio** (por ejemplo `GEYPE\svc_revisor`), sin
  privilegios de administrador, con lectura y escritura en las carpetas del punto 2.

## 2. Carpetas

Las dos carpetas tienen que estar **una al lado de la otra**:

```
D:\GEyPE\                                  (o la ruta que se prefiera)
├── Comprobación_SSAA_facturas\            la app (repositorio de GitHub)
└── Descarga_datos_ESIOS\                  scripts y Excel de ESIOS
```

1. App: `git clone https://github.com/iyadazig/validador_SSAA_facturas.git Comprobación_SSAA_facturas`
2. Datos de ESIOS: copiar la carpeta `Descarga_datos_ESIOS` completa desde el ordenador
   de Noelia (scripts, Excel históricos y `esios_token.txt`).
3. Fichas de contrato ya existentes: copiar `contratos_ssaa.json` del ordenador de Noelia a
   `Comprobación_SSAA_facturas\`. Al primer arranque se importan a la base de datos.

> `contratos_ssaa.json`, la base de datos y los Excel contienen **datos de clientes**:
> copiarlos por una carpeta compartida interna, nunca por correo ni servicios externos.

## 3. Librerías de Python

En una consola, desde `Comprobación_SSAA_facturas`:

```bat
python -m pip install -r requirements.txt
```

## 4. Credenciales

- **ESIOS**: el fichero `Descarga_datos_ESIOS\esios_token.txt` (o la variable de entorno
  `ESIOS_TOKEN` de la cuenta del servicio).
- **Gemweb**: variables de entorno `GEMWEB_CLIENT_ID` y `GEMWEB_CLIENT_SECRET` de la cuenta
  del servicio, **o** después del primer arranque, un administrador las introduce en la app
  (barra lateral → Gemweb → Configurar credenciales); quedan cifradas en el perfil de esa
  cuenta.

Las credenciales no van nunca al repositorio de GitHub.

## 5. Instalación (cortafuegos y arranque automático)

En PowerShell **como administrador**, desde `Comprobación_SSAA_facturas`:

```powershell
powershell -ExecutionPolicy Bypass -File servidor\instalar_servidor.ps1 `
    -Subredes "192.168.0.0/24,10.8.0.0/24" -Usuario "GEYPE\svc_revisor"
```

- `-Subredes`: la red de la oficina **y** el rango de direcciones de la VPN. Solo esas
  direcciones podrán abrir la app; desde internet no es accesible.
- `-Usuario`: la cuenta del servicio (pedirá su contraseña).
- Opcionales: `-Puerto 8501`, `-Python "C:\ruta\python.exe"`, `-CarpetaEsios`, `-CarpetaCopias`.

El script crea:

| Tarea programada | Cuándo | Qué hace |
|---|---|---|
| Revisor SSAA - servidor | Al encender (y se reinicia si se cae) | La app en el puerto 8501 |
| Revisor SSAA - descarga PVPC diaria | Todos los días, 08:30 | Total SAH del PVPC_DETALLE |
| Revisor SSAA - descarga componentes ESIOS | Lunes, 09:00 | Componentes, PFMHORAS_COM (y su C2), pérdidas |
| Revisor SSAA - copia de seguridad | Todos los días, 23:00 | Copia de la base de datos (se guardan 30) |

## 6. VPN

La VPN da acceso a las carpetas del servidor (puerto 445), pero la app usa **otro puerto**:
hay que permitir en la VPN el tráfico **TCP 8501** hacia el servidor. Comprobación desde un
equipo conectado por VPN:

```powershell
Test-NetConnection SERVIDOR -Port 8501
```

(`TcpTestSucceeded : True`).

## 7. Primer acceso y usuarios

1. Abrir `http://SERVIDOR:8501` (en el servidor, `http://localhost:8501`).
2. La primera vez la app pide **crear el administrador** (usuario, nombre y contraseña).
3. El administrador da de alta al resto en **Usuarios**: la app genera una contraseña
   provisional que hay que darles en persona o por teléfono; al entrar, cada uno la cambia.
4. Contraseñas: mínimo 10 caracteres, con letras y números. Tras 5 intentos fallidos el
   usuario queda bloqueado 15 minutos. Un administrador puede restablecer contraseñas y
   desactivar usuarios (por ejemplo, si alguien deja la empresa).

A cada compañero basta con darle el enlace `http://SERVIDOR:8501` para guardarlo en
favoritos.

## 8. Comprobar que todo funciona

```bat
python lanzador.py --autoprueba
type autoprueba_resultado.txt
```

Todas las líneas deben empezar por `OK` (lectura de ESIOS, cálculo, gráfica, informe,
fichas, lectura de PDF).

## 9. Actualizar la aplicación

```bat
cd D:\GEyPE\Comprobación_SSAA_facturas
git pull
python -m pip install -r requirements.txt
schtasks /End /TN "Revisor SSAA - servidor"
schtasks /Run /TN "Revisor SSAA - servidor"
```

Los compañeros solo tienen que recargar la página.

## 10. Copias de seguridad

- Cada noche se copia `revisor_ssaa.db` en `Comprobación_SSAA_facturas\copias_seguridad\`
  (se conservan las 30 últimas). Conviene incluir esa carpeta en la copia de seguridad
  general de la empresa.
- Copia manual: `python almacen.py --copia D:\ruta\de\copias`
- **Restaurar**: parar la tarea del servidor, sustituir `revisor_ssaa.db` por la copia
  elegida (renombrándola) y volver a arrancar la tarea.

## 11. HTTPS (recomendado)

Por la VPN el tráfico ya va cifrado; dentro de la oficina, sin HTTPS, las contraseñas
viajan en claro por la red local. Para activarlo, con un certificado de la CA interna (o
uno autofirmado) en formato PEM:

1. Definir para la cuenta del servicio las variables `SSAA_SSL_CERT` (ruta del certificado)
   y `SSAA_SSL_KEY` (ruta de la clave privada).
2. Reiniciar la tarea «Revisor SSAA - servidor».
3. La dirección pasa a ser `https://SERVIDOR:8501`.

## 12. Problemas frecuentes

| Síntoma | Causa probable |
|---|---|
| Desde la oficina no abre | Tarea parada (ver el Programador de tareas) o regla del cortafuegos con otra subred |
| Desde casa no abre y en la oficina sí | La VPN no deja pasar el puerto 8501 (punto 6) |
| «Faltan días de … en los Excel» | Las tareas de descarga de ESIOS no se están ejecutando o falta `esios_token.txt` |
| Gemweb sin credenciales | Punto 4 |
| Olvido de contraseña | Un administrador la restablece en «Usuarios» |
| Nadie es administrador | No puede pasar: la app impide quitar o desactivar al último administrador |
