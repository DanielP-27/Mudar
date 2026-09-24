# Runbook de despliegue — MUDAR V1.0

Procedimiento para levantar MUDAR sobre Ubuntu Server 24.04: Django + Gunicorn + Nginx + PostgreSQL.
Se escribe durante el ensayo en WSL (bloque C) y se ejecuta después en el servidor de GTD (bloque D).

**Reglas de este archivo**

- **Ningún secreto.** Las contraseñas, la `SECRET_KEY` y las credenciales van en `/etc/mudar/env` (600, root), nunca aquí.
- **Cada paso tiene su apartado «Verificación».** Un paso no está terminado hasta que sus comprobaciones dan el resultado esperado.
- **Las trampas previsibles se citan como T1 a T15** (listado al final). Cada una se verifica en el paso que la cubre.
- **La prueba de que el runbook está completo es el paso 15:** borrar el entorno y repetirlo todo leyendo solo este archivo.

---

## 1. Decisiones previas ✅

- Código en `/opt/mudar`, con dueño `root` (755 para directorios y 644 para archivos). El usuario de servicio `mudar` solo lee.
- Configuración con secretos en `/etc/mudar/env` (600, root). systemd la lee como root antes de cambiar al usuario de servicio.
- Registros de la aplicación en `/var/log/mudar`.
- Este runbook vive en `despliegue/RUNBOOK.md`, en el repositorio.

## 2. Instalar WSL con Ubuntu 24.04 ✅

**Comandos** (solo en el ensayo; en el servidor de GTD el sistema ya viene instalado)
- En PowerShell como administrador: `wsl --install -d Ubuntu-24.04`.
- No hizo falta reiniciar, porque la plataforma de máquina virtual de Windows ya estaba activa. Se comprueba con `wsl --list --verbose`: la distribución debe aparecer `Running` en la versión 2.
- La primera vez que se abre, Ubuntu pide crear un usuario administrador (minúsculas, sin tildes) y su contraseña, que es la que pedirá `sudo`.

**Resultado del ensayo (2026-09-19):** `running` · Ubuntu 24.04.5 LTS (noble) · Python 3.12.3.

**Verificación**
- `systemctl is-system-running` responde `running` o `degraded`, no un error: systemd está activo.
- `lsb_release -a` muestra Ubuntu 24.04.
- `python3 --version` muestra 3.12.

## 3. Sistema base ✅

**Comandos**
- 3.1 Actualizar: `sudo apt update && sudo apt upgrade -y`. Para comprobar: `apt list --upgradable` no lista nada y `/var/run/reboot-required` no existe.
- 3.2 Zona horaria: `sudo timedatectl set-timezone America/Bogota`. No imprime nada si sale bien.
- 3.3 Reloj (NTP): en Ubuntu 24.04 ya viene activo (`systemd-timesyncd`), no hubo que hacer nada. Se comprueba con `timedatectl`. ⚠️ En el servidor, la salida restringida de GTD tiene que dejar pasar el puerto 123/UDP.
- 3.4 Diario persistente: `/var/log/journal` ya existe en la imagen de Ubuntu 24.04, así que el diario se guarda en disco. Si no existiera: `sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald`.
- 3.5 Locale: `sudo locale-gen es_CO.UTF-8`. Deja el locale disponible, pero no cambia el idioma del sistema.

**Resultado del ensayo (2026-09-19):** zona `America/Bogota (-05)`, `System clock synchronized: yes`, `NTP service: active`; diario de 23,6 MB en disco; `locale -a` lista `C`, `C.utf8`, `POSIX` y `es_CO.utf8`.

**Verificación**
- `timedatectl` muestra la zona `America/Bogota` y `System clock synchronized: yes`. `date` coincide con la hora de Windows. **(T13)**
- `/var/log/journal` existe y `journalctl --disk-usage` informa del uso en disco, no en `/run`. **(T8)**
- `locale -a` incluye `es_CO.utf8`. **(T5)**

## 4. Usuario de servicio y directorios ✅

**Comandos** (en este orden: la cuenta tiene que existir antes de asignarle directorios)
- 4.1 Usuario de servicio: `sudo adduser --system --group --no-create-home mudar`. La salida debe incluir `Adding new group 'mudar'`.
  ⚠️ Si falta `--group`, la cuenta se crea igual pero queda en el grupo compartido `nogroup` (gid 65534), y `adduser` no avisa. Se corrige con `sudo deluser mudar` y repitiendo el comando completo.
- 4.2 Código y registros:
  ```
  sudo mkdir -p /opt/mudar /var/log/mudar
  sudo chown mudar:mudar /var/log/mudar
  sudo chmod 750 /var/log/mudar
  ```
  `/opt/mudar` se queda en `root:root` 755 (`mudar` lee el código pero no lo modifica). `/var/log/mudar` queda en `mudar:mudar` 750, porque `seguridad.log` guarda usuarios e IPs. Para leer los registros hace falta `sudo`; `fail2ban` corre como root y no se ve afectado.
- 4.3 Configuración con secretos:
  ```
  sudo mkdir -p /etc/mudar
  sudo touch /etc/mudar/env
  sudo chmod 600 /etc/mudar/env
  ```
  El archivo queda vacío hasta el paso 7. Es de `root` y no de `mudar` porque quien lo lee es systemd, como root, antes de cambiar al usuario de servicio. El `chmod` va **antes** de escribir cualquier secreto, porque `touch` lo crea con 644.

**Resultado del ensayo (2026-09-19):** `mudar` uid 105 / gid 108 · `/opt/mudar` `root:root` 755 · `/var/log/mudar` `mudar:mudar` 750 · `/etc/mudar` `root:root` 755 · `/etc/mudar/env` `root:root` 600, 0 bytes. `ls /var/log/mudar` y `cat /etc/mudar/env` dan `Permission denied` sin `sudo`, que es lo esperado.

**Verificación**
- `getent passwd mudar` muestra un usuario de sistema con shell `nologin`.
- `id mudar` muestra `gid=…(mudar)`, **no** `nogroup`.
- `ls -ld /opt/mudar /var/log/mudar /etc/mudar` muestra el dueño y los permisos declarados en el paso 1.
- `/etc/mudar/env` está en 600 y es de root. Los valores van sin comillas y sin `#`, `$` ni `\`. **(T10: aquí se previene; se verifica en el paso 8)**

## 5. PostgreSQL ✅

**Comandos**
- 5.1 Instalar: `sudo apt install -y postgresql`. Crea el usuario de Linux `postgres` y el clúster `16/main`, y lo deja activo y habilitado. Antes de instalar, `apt-cache policy postgresql-16` muestra la versión que se va a instalar **(T7)**.
- 5.2 Rol de la aplicación:
  ```
  openssl rand -hex 24
  sudo -u postgres createuser --pwprompt mudar_app
  ```
  La contraseña se genera en hexadecimal **(T10)** y se guarda fuera de la terminal; en el paso 7 va a `/etc/mudar/env`. Hay que comprobar que tenga 48 caracteres. Para verificar: `sudo -u postgres psql -c "\du"` muestra `mudar_app` con la columna de atributos vacía.
- 5.3 Base de datos:
  ```
  sudo -u postgres createdb --owner=mudar_app --encoding=UTF8 --locale=es_CO.UTF-8 --template=template0 mudar_db
  ```
  `template0` es obligatorio: `template1` tiene el locale `C.UTF-8` y no admite que se le cambie al copiarla. La base queda vacía; las tablas las crea `migrate` en el paso 7. Para verificar: `sudo -u postgres psql -l` **(T5)**.
- 5.4 `pg_hba.conf`: **no se edita.** La configuración de fábrica de Ubuntu 24.04 ya aplica `peer` en el socket local y `scram-sha-256` por TCP desde `127.0.0.1` y `::1`, sin ninguna línea `trust`. Para ver las reglas activas: `sudo grep -Ev '^\s*(#|$)' /etc/postgresql/16/main/pg_hba.conf`.
  Pruebas **(T6)**: `psql -h localhost -U mudar_app -d mudar_db -w` da `no password supplied` · `psql -U mudar_app -d mudar_db` (socket) da `Peer authentication failed` · con contraseña, `psql -h localhost -U mudar_app -d mudar_db -c "select current_user;"` responde `mudar_app`.
- `psql` muestra las tablas anchas en el paginador; si aparece `(END)`, se sale con `q`.

**Resultado del ensayo (2026-09-19):** PostgreSQL 16.15, clúster `16/main` online, escucha solo en `127.0.0.1:5432` · `mudar_app` sin atributos · `mudar_db` con dueño `mudar_app`, `UTF8` y `es_CO.UTF-8`.

**Verificación**
- `psql --version` muestra 16.9 o posterior. **(T7)**
- `\l` muestra `mudar_db` con collation y ctype `es_CO.UTF-8`. **(T5)**
- `sudo -u postgres psql` entra sin contraseña (`peer`). **(T6)**
- `psql -h localhost -U mudar_app mudar_db` pide contraseña (`scram-sha-256`). **(T6)**

## 6. Código y entorno de Python ✅

**Comandos**. El repositorio se clona desde GitHub dentro de Linux, nunca se copia desde `C:\`.
- 6.1 Soporte de entornos virtuales: `sudo apt install -y python3.12-venv`. Ubuntu 24.04 no lo trae instalado, y sin él la creación del entorno falla con `ensurepip is not available`.
- 6.2 Clonar: `sudo git clone https://github.com/DanielP-27/Mudar.git /opt/mudar`. `/opt/mudar` tiene que estar vacía. Todo queda con dueño `root`.
  ⚠️ Las operaciones de git en `/opt/mudar` se hacen **con `sudo`**. Sin él, git responde `detected dubious ownership` porque el repositorio es de otro usuario. No se añade una excepción con `safe.directory`.
- 6.3 Entorno virtual y dependencias:
  ```
  sudo python3 -m venv /opt/mudar/venv
  sudo /opt/mudar/venv/bin/pip install -r /opt/mudar/requirements.txt
  ```
  El entorno queda con dueño `root`. Se usa por ruta completa (`/opt/mudar/venv/bin/...`), sin `activate`, porque la activación no se conserva a través de `sudo`. Para verificar: `pip freeze` del entorno coincide con `requirements.txt` y `pip check` responde `No broken requirements found`.
- Las pruebas **no** van en este paso: necesitan `SECRET_KEY` y `DB_*`, que se escriben en el paso 7. Se movieron allí el 2026-09-19.

**Resultado del ensayo (2026-09-19):** commit `3c0f3eb` · sin CRLF · 12 paquetes idénticos a `requirements.txt` · psycopg2 2.9.11 y Django 5.2.17 cargan con Python 3.12.3.

**Verificación**
- `ls -l /opt/mudar` muestra dueños y permisos reales, no 777. **(T12)**
- `sudo git -C /opt/mudar log -1 --oneline` muestra el commit que se quería desplegar.
- `file /opt/mudar/manage.py /opt/mudar/despliegue/*.service` no dice `with CRLF line terminators`. **(T12)**

## 7. Variables de entorno, pruebas y base inicial ✅

**Orden** (cambiado el 2026-09-19): 7.1 escribir `/etc/mudar/env` → 7.2 las pruebas (solo en el ensayo) → 7.3 `check --deploy` → 7.4 `migrate` → 7.5 semilla → 7.6 `collectstatic`.

**Cómo se ejecuta `manage.py`.** Nunca con `sudo python manage.py`: los registros quedarían con dueño `root`, y `mudar` no podría escribir en ellos después. Tampoco como `mudar` a secas, porque no puede leer `/etc/mudar/env`. Se usa `systemd-run`, que hace lo mismo que el servicio de Gunicorn: systemd, como root, lee el archivo de secretos y después ejecuta la orden como `mudar`.
```
sudo systemd-run --uid=mudar --gid=mudar --wait --pipe --collect \
  --property=EnvironmentFile=/etc/mudar/env \
  --working-directory=/opt/mudar \
  /opt/mudar/venv/bin/python manage.py <orden>
```
- `--wait --pipe` hacen que la salida aparezca en la terminal y que el comando espere a que la orden termine. `--collect` limpia la unidad temporal al terminar.
- Si una orden funciona así, el camino de los secretos ya está probado antes del paso 8.

**`CREATEDB` durante las pruebas (solo en el ensayo).** Las pruebas crean la base temporal `test_mudar_db`, y `mudar_app` no puede crear bases. Se le concede el permiso antes de las pruebas y se le retira al terminar, **siempre**, aunque las pruebas fallen:
```
sudo -u postgres psql -c "ALTER ROLE mudar_app CREATEDB;"
sudo -u postgres psql -c "ALTER ROLE mudar_app NOCREATEDB;"
```
En el servidor de GTD no se concede nunca, porque allí no se corren las pruebas.

**Las pruebas se corren con `DEBUG=True`** (decidido el 2026-09-19). Con `DEBUG=False`, `SECURE_SSL_REDIRECT` (`settings.py:207`) respondería 301 a las peticiones HTTP simuladas de las pruebas. `/usr/bin/env` sustituye solo esa variable y solo para esa orden; el archivo no se toca:
```
sudo systemd-run --uid=mudar --gid=mudar --wait --pipe --collect \
  --property=EnvironmentFile=/etc/mudar/env \
  --working-directory=/opt/mudar \
  /usr/bin/env DEBUG=True /opt/mudar/venv/bin/python manage.py test
```
Las pruebas verifican la lógica de negocio. La capa de seguridad de producción la verifican el 7.3 (`check --deploy`) y el paso 10.

**Resultado del ensayo 7.2 (2026-09-19):** `OK`, `status=0`, 1 min 3 s. La plantilla de `systemd-run` funcionó a la primera, así que los secretos llegan bien desde el archivo **(T10)**. `CREATEDB` concedido, verificado con `\du` y retirado. `Ran 316 tests`.

**Comandos**
- 7.3 `check --deploy`, **sin** `DEBUG=True`:
  ```
  sudo systemd-run --uid=mudar --gid=mudar --wait --pipe --collect --property=EnvironmentFile=/etc/mudar/env --working-directory=/opt/mudar /opt/mudar/venv/bin/python manage.py check --deploy
  ```
  Resultado esperado: solo `security.W005` (HSTS sin subdominios) y `security.W021` (sin *preload*). Las dos son decisiones conscientes, porque `mudarcolombia.com` aloja otros servicios que no son nuestros. **Resultado del ensayo (2026-09-19): exactamente esas dos.**
- 7.4 `migrate`: la misma plantilla con `manage.py migrate`. Después, dos confirmaciones que deben terminar en `status=0`:
  - `manage.py migrate --check` mira la **base**: no queda ninguna migración pendiente.
  - `manage.py makemigrations --check --dry-run` mira el **código**: responde `No changes detected`, es decir, los modelos coinciden con las migraciones.

  **Resultado del ensayo (2026-09-19):** 30 migraciones de `server` (de la 0001 a la 0030, las mismas que el repositorio) más las de Django. Las dos confirmaciones dieron `status=0`.
- 7.5 Semilla, con el `semilla.json` real (decidido el 2026-09-19). El archivo no viaja en git: sale del respaldo cifrado.
  1. Colocarlo con atributos explícitos, sin heredarlos **(T12)**. En el ensayo se copia desde `/mnt/c`; en el servidor llega por `scp` a una ruta temporal.
     ```
     sudo install -o root -g mudar -m 640 <origen>/semilla.json /opt/mudar/server/semilla/semilla.json
     ```
  2. Sembrar: la plantilla con `manage.py sembrar`. El comando exige una base vacía y carga todo o nada.
  3. Contraseñas: la plantilla con **`--pty` en lugar de `--pipe`** y `manage.py changepassword <USUARIO>`. Sin terminal, la contraseña podría verse al escribirla. El nombre de usuario distingue mayúsculas. En el ensayo solo `ADMINISTRADOR`; **en el servidor, los 9 usuarios.** ⚠️ Pegar con `Ctrl+Shift+V`, porque `Ctrl+C` interrumpe el comando.
  4. Borrar `semilla.json` del servidor una vez cargada (decidido el 2026-09-19): `sudo rm /opt/mudar/server/semilla/semilla.json`. Los datos ya viven en la base y en su respaldo, y `sembrar` no vuelve a cargar sobre una base con filas. La copia buena es la cifrada. `ejemplo.json` se queda, porque es del repositorio.

  **Verificación de la semilla:**
  ```
  sudo -u postgres psql -d mudar_db -c "select turno_id, nombre_turno from turnos order by turno_id;" -c "select last_value from turnos_turno_id_seq;" -c "select u.username, p.rol, u.is_active, left(u.password,1) as pw from auth_user u join perfiles_usuario p on p.user_id = u.id order by p.rol;"
  ```
  Turnos con id 1 y 3 · contador en 3 · antes de `changepassword`, todos los usuarios con `!`.

  **Resultado del ensayo (2026-09-19):** 9 usuarios, 9 perfiles, 7 familias, 2 turnos, 55 clientes, 37 listas y 29 productos. Turnos 1 y 3, contador en 3. Contraseña de `ADMINISTRADOR` creada.
- 7.6 `collectstatic`, **como root**: la plantilla sin `--uid` ni `--gid`. `STATIC_ROOT` es `/opt/mudar/staticfiles`, dentro de una carpeta de root, y los estáticos se tratan como el código: `mudar` los lee pero no los modifica.
  ```
  sudo systemd-run --wait --pipe --collect --property=EnvironmentFile=/etc/mudar/env --working-directory=/opt/mudar /opt/mudar/venv/bin/python manage.py collectstatic --noinput
  ```
  Solo recoge los estáticos del panel y de DRF. El frontend de React es el `dist/` del paso 9. Hay que repetirlo cada vez que se actualice Django.

  **Resultado del ensayo (2026-09-19):** 163 archivos en `admin/` y `rest_framework/`, todos de `root`. `admin/css/base.css` tiene permisos 644 **(T2: el archivo existe; que Nginx lo reenvíe se prueba en el paso 10)**.

**Verificación**
- La `SECRET_KEY` se generó sin `#`, `$`, `\` ni comillas. **(T10)**
- Las 316 pruebas pasan con Python 3.12 (solo en el ensayo).
- Después de las pruebas, `sudo -u postgres psql -c "\du"` vuelve a mostrar `mudar_app` sin atributos.
- `python manage.py check --deploy` termina sin errores. Las advertencias se revisan una por una.
- `python manage.py showmigrations` no deja ninguna migración sin aplicar.
- La semilla deja las siete tablas de configuración, con los turnos con id 1 y 3.

## 8. Gunicorn como servicio ✅

**Decisiones tomadas el 2026-09-21/22. Se escriben aquí porque viajan dentro de la unidad y en D se copia tal cual.**

- **Canal con Nginx: puerto TCP en `127.0.0.1:8000`** (opción A), no socket Unix. Motivos: cada capa se
  verifica por separado con un `curl` normal, y el socket añade una superficie de permisos más. Lo que se
  renuncia: un proceso que ya corra dentro de la máquina puede hablar con Django saltándose el `limit_req`
  de Nginx. Se analizó y se acepta: los dos atacantes locales plausibles o están invitados por diseño
  (`www-data`, que necesita el acceso para que haya aplicación) o ya poseen lo que se protegería
  (`mudar`, `postgres`). **La publicación accidental del 8000 no basta para exponerlo**: haría falta además
  un `--bind` mal escrito, y eso se comprueba con `ss -ltnp`.
- **`--workers 3`** *(cerrado por Angel el 2026-09-22, tras analizar la concurrencia real)*. La máquina de
  GTD son 2 núcleos y 4 GB compartidos con PostgreSQL; la fórmula habitual (2×núcleos+1) daría 5 workers,
  más el maestro aparte.
  **El cálculo que lo decide:** 9 usuarios no son 9 peticiones simultáneas. Con un ritmo alto para una
  aplicación de captura —una petición cada 5 s por usuario— son 1,8 peticiones/s; a 250 ms de media, eso son
  **0,45 peticiones en vuelo a la vez**. Ni triplicando el ritmo se llega a 2.
  **El único escenario que lo rompería** es un pico sincronizado (varios abriendo el dashboard en el mismo
  segundo), y ahí el culpable no es el número de usuarios sino **el N+1 del dashboard**, que dura ~1,2 s y
  por eso coincide con todo lo que llegue en esa ventana. Angel lo descarta por hipotético; la solución real
  a ese caso es arreglar el N+1, ya anotado como deuda post-V1.0.
  ⚠️ **Dos argumentos que se dieron y NO son válidos, para no repetirlos:** que 5 workers «pelearían por dos
  núcleos» (un worker esperando a PostgreSQL no ocupa núcleo, y esta carga es sobre todo espera) y que no
  cabrían en memoria (5 x ~150 MB son ~750 MB sobre 4 GB; no es el límite).
  **Límite que conviene recordar:** en un pico grande, más workers no aumentan el trabajo total —eso lo fijan
  los 2 núcleos y PostgreSQL—, solo reparten la espera de otra forma.
  Revisable con medidas reales después del despliegue: es un número y un reinicio.
  *Esquema de apoyo: `Descargas/Esquema_workers_nucleos_MUDAR.html`.*
- **`--timeout 30`, el de fábrica** *(decisión de Angel el 2026-09-22, revisando la propuesta inicial de 60)*.
  El temporizador es un **vigilante, no un presupuesto por petición**: el maestro mata al worker que lleve 30 s
  sin dar señales de vida. Se sigue la convención y **se decide con medidas, no con suposiciones**: si el N+1
  del dashboard (100-250 consultas por carga) lo excede en producción, se sube entonces.
  **Riesgo aceptado:** si una carga legítima pasa de 30 s, el usuario ve un 502 y el worker se reinicia.
  **Ata el paso 10: `proxy_read_timeout` >= 30 (T4)** — y si un día se sube el timeout, hay que subir los dos.
  **Para poder medirlo hace falta el punto siguiente**: el formato por omisión del registro de acceso no
  incluye la duración de la petición.
- **`--access-logfile -`**, a la salida estándar y de ahí a journald. Journald ya rota solo y el registro de
  acceso con la IP real lo llevará Nginx. **Con `--access-logformat`: el formato de fábrica más `%(L)s` al
  final**, que es la duración en segundos con decimales. Es el dato con el que se revisará el `--timeout`;
  sin él, dentro de un mes no habría con qué decidir. `%(h)s` mostrará siempre `127.0.0.1` porque quien habla
  con Gunicorn es Nginx — eso es correcto, no un fallo.
  ⚠️ **En el archivo de unidad hay que escribirlo con `%%`**: en systemd el `%` introduce un especificador,
  así que un `%(h)s` literal se escribe `%%(h)s`.
  Explotación posterior, con la duración como último campo:
  `journalctl -u mudar-web --since "-7 days" --no-pager | awk '{print $NF, $0}' | sort -rn | head -20`
- **Blindaje de systemd — una sola tanda, la de riesgo nulo** *(decisión de Angel el 2026-09-22)*.
  Verificado antes de decidirlo que lo único que la aplicación necesita escribir es `/var/log/mudar`: la
  conexión a PostgreSQL es **TCP** (`DB_HOST` por defecto `localhost`, `settings.py:88`), no hay `MEDIA_ROOT`
  y `collectstatic` se ejecuta aparte como root, no por la unidad.
  **Se incluyen:** `NoNewPrivileges` · `PrivateTmp` · `ProtectHome` · `ProtectSystem=strict` con
  `ReadWritePaths=/var/log/mudar` · `CapabilityBoundingSet=` y `AmbientCapabilities=` **vacíos** (posible
  porque el puerto es 8000 y no el 80: el servicio no necesita ninguna capacidad) · `ProtectClock`
  (el reloj sostiene la caducidad del token y todo el cálculo de cronómetros) · `PrivateDevices` ·
  `ProtectKernelTunables` · `ProtectKernelModules` · `ProtectKernelLogs` · `ProtectControlGroups` ·
  `RestrictNamespaces` · `RestrictSUIDSGID` · `RestrictRealtime` · `LockPersonality` ·
  `SystemCallArchitectures=native` · `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX AF_NETLINK`
  (bloquea `AF_PACKET`, es decir capturar el tráfico de loopback que lleva la contraseña de la base;
  ⚠️ **`AF_NETLINK` es obligatorio**: glibc lo usa para resolver nombres y sin él se rompe el DNS del correo).
  **Se aplazan a después de la V1.0**, por poder romper de forma difícil de diagnosticar:
  `SystemCallFilter=@system-service`, `ProtectProc=invisible` y `ProcSubset=pid`. Cuando se retomen, con el
  mismo método: una tanda cada vez y `systemd-analyze security` antes y después.
  **Descartadas con motivo:** `IPAddressDeny` (el correo va a Office 365, cuyas IP cambian; esa restricción
  ya vive mejor en el borde de GTD) · `MemoryDenyWriteExecute` (rompe con CPython y el fallo es oscuro) ·
  `PrivateUsers` (añade poco y complica los permisos del registro) · `PrivateNetwork` (imposible, hace falta red).
- **Nombre del archivo: `mudar-web.service`**, en línea con `mudar-cronometros.service`; nombra el papel y no
  la herramienta.
- **`LogsDirectory=mudar` con `LogsDirectoryMode=0750`** *(2026-09-22)*. systemd crea `/var/log/mudar` en cada
  arranque con el dueño del servicio, así la unidad no depende del paso manual del paso 4 — una cosa menos que
  recordar en D. Y una carpeta declarada así queda escribible bajo `ProtectSystem=strict` **sin** necesidad de
  `ReadWritePaths`.
- **`MemoryMax` sí, `MemoryHigh` no** *(2026-09-22)*. La aplicación y PostgreSQL comparten 4 GB: sin techo, una
  fuga de Django haría que el kernel eligiera víctima, y podría ser un proceso de la base. Con `MemoryMax` el
  que muere está dentro del grupo de control del servicio, PostgreSQL no se entera y `Restart=always` levanta
  en 5 s dejando rastro en `journalctl`.
  **`MemoryHigh` se descarta porque su aviso no lo vería nadie:** no escribe línea de alerta ni dispara el
  correo de B6 (que va con los `ERROR` de Django), así que produciría una aplicación viva pero lenta **en
  silencio**, más difícil de diagnosticar que una caída. Además, frenar reclamando memoria rinde poco sin
  espacio de intercambio, y no sabemos si la máquina de GTD lo traerá. **Se reconsidera el día que exista algo
  que vigile el servidor y avise.**
  ⚠️ **El valor no se fija a ojo:** se mide la memoria real en el 8.3 con `systemctl status mudar-web` y se
  declara en el 8.5 sobre ese dato. Referencia de partida: pico legítimo estimado ~600 MB con 3 workers.
- **`--preload`: decidido que sí** al escribir la unidad.
- **`Type=notify`** *(2026-09-22)*. systemd no da el servicio por arrancado hasta que Gunicorn avisa de que
  atiende. Con `simple` (el de fábrica) lo daría por bueno al crear el proceso, así que **un fallo de
  importación con `--preload` —una variable que falte en `/etc/mudar/env`— devolvería éxito** y aparecería
  tres subpasos después. Si Gunicorn no mandara el aviso, `systemctl start` se colgaría ~90 s y el servicio
  saldría fallido aun funcionando: salida, `Type=exec`.
- **`KillMode=mixed` con `TimeoutStopSec=35`** *(2026-09-22)*. La señal de parada va **solo al maestro**, que
  cierra a sus workers dejando terminar lo que esté en curso; por omisión systemd se la mandaría a todos a la
  vez. Importa por los PUT atómicos de planeación y de la etapa 4: cortarlos no deja la base a medias, pero el
  usuario pierde el guardado. ⚠️ **Los 35 s no son arbitrarios:** Gunicorn da 30 a sus workers y `--timeout`
  también es 30, así que un plazo menor mataría a mitad del cierre ordenado y anularía el `mixed`.
- **Sin `ExecReload`, a propósito** *(2026-09-22)*. Con `--preload`, la señal HUP reinicia los workers pero
  **no relee el código**: un `systemctl reload` respondería «hecho» y seguiría sirviendo la versión anterior.
  Se prefiere que la orden no exista a que exista y mienta. **Para desplegar código nuevo: `systemctl restart`.** Comparte más memoria entre workers (copia al
  escribir); impide recargar código sin reiniciar, cosa que aquí no molesta.

**Comandos:** _pendiente_

**Secuencia de siete subpasos** *(aprobada el 2026-09-22)*. El reparto es el de la sesión 1: Angel ejecuta
lo que lleva `sudo`, Claude verifica desde fuera con `wsl -d Ubuntu-24.04 -- …` y anota aquí.

- **8.1** — Escribir `despliegue/mudar-web.service` **sin el blindaje**, en Windows. Revisión línea a línea
  antes de instalar nada.
- **8.2** — Instalar: copiar a `/etc/systemd/system/`, `daemon-reload`, `enable --now`.
- **8.3** — Verificar la base: `ss -ltnp` (8000 **solo** en 127.0.0.1) · `curl` con cabecera `Host` → 401 ·
  `journalctl -u mudar-web` sin excepciones · `systemctl cat` con workers y timeout explícitos.
  **Punto conocido bueno: si algo falla después, se vuelve aquí.**
- **8.4** — `systemd-analyze security mudar-web.service` **antes** del blindaje; anotar la puntuación.

**✅ 8.1 a 8.3 cerrados el 2026-09-22.** Ciclo de instalación: `install -o root -g root -m 644` desde
`/mnt/c/...` → `daemon-reload` → `enable --now`. `systemd-analyze verify` salió vacío, lo que confirma que el
escape `%%` se parseó bien. Servicio `active (running)`, 4 tareas (maestro + 3 workers), escuchando **solo** en
`127.0.0.1:8000`, y `Status: "Gunicorn arbiter booted"` — o sea que **`Type=notify` funcionó**. El cierre
ordenado del `KillMode=mixed` se ve en el journal: la señal la recibe solo el maestro y él hace salir a los
tres workers.

**Dos hallazgos del ensayo, los dos resueltos el mismo día:**
1. **Gunicorn 26 trae un socket de control activado de fábrica** en `/run/user/<uid>`, ruta que presupone un
   usuario con sesión iniciada. Como `mudar` es de sistema (`nologin`, hogar `/nonexistent`), cada arranque
   dejaba `[ERROR] Control server error: [Errno 13] Permission denied: '/nonexistent'`. **Resuelto con
   `--no-control-socket`.** Efecto medido: la memoria del servicio bajó de **78 MB a 44,4 MB**.
2. **WSL había devuelto la zona horaria a `Europe/Madrid`**, pisando el `America/Bogota` del paso 3 (sincroniza
   desde Windows, y Angel está en Huelva). El síntoma era que journald marcaba CEST y Gunicorn `-0500` — porque
   **Django cambia la zona del proceso** al leer `TIME_ZONE`, así que la aplicación iba en hora de Colombia y el
   sistema en hora de España. Los datos no corrían peligro (`USE_TZ=True`, todo en UTC).
   ⚠️ **Por qué importa, y es del paso 11: los temporizadores de systemd usan la zona del SISTEMA OPERATIVO,
   no la de Django.** Con la máquina en hora de Madrid, `mudar-cronometros.timer` habría disparado su
   `OnCalendar=…21:00:00` a las **14:00 de Bogotá**. Resuelto con `timedatectl set-timezone America/Bogota`.
   **Falta comprobar en el 8.7 si sobrevive al reinicio de WSL**; si WSL la vuelve a pisar, hay que fijarla.

**📏 Línea de referencia para el `MemoryMax` del 8.5:** ~**45 MB** en reposo, el servicio entero (maestro y
tres workers). La estimación previa de ~600 MB era muy alta: el mérito es de `--preload`, que hace que los
workers compartan físicamente la memoria.

**🔴 Requisito nuevo para el paso 10, descubierto aquí.** Con `DEBUG=False`, `SECURE_SSL_REDIRECT=True` hace que
Django responda **301 a `https://`** a cualquier petición que no venga marcada como segura. La prueba con
`curl` lo reprodujo, y se resolvió añadiendo `-H "X-Forwarded-Proto: https"`, que es lo que activa el
`SECURE_PROXY_SSL_HEADER` de `settings.py:206`. **Por tanto Nginx tiene que enviar
`proxy_set_header X-Forwarded-Proto $scheme;` además del `X-Forwarded-For` de 9.5** — sin esa línea, todo
responde 301 en bucle. Bonus: el mecanismo queda probado antes de existir Nginx.

**Verificación final del 8.3, con la cabecera puesta:** `401 Unauthorized` con `WWW-Authenticate: Token`, y el
registro de acceso escribiendo **valores reales**, con la duración al final:
`127.0.0.1 - - [22/Sep/2026:11:43:59 -0500] "GET /api/auth/perfil/ HTTP/1.1" 401 65 "-" "curl/8.5.0" 0.228729`
Las dos peticiones las atendieron workers distintos (881 y 879). *(También se vio `Strict-Transport-Security:
max-age=3600`, el HSTS de una hora que sube a un año el día del despliegue — CLAUDE.md 9.4.)*
- **8.5** — Añadir el blindaje, recargar, reiniciar y repetir el análisis para ver qué cambió.
- **8.6** — Verificar que el blindaje no rompió nada: las cuatro del 8.3 más los dos caminos de riesgo —
  **un login real** (toca la base) y **una resolución de nombre** (valida `AF_NETLINK`).
- **8.7** — `wsl --shutdown`, volver a entrar, comprobar arranque automático y `journalctl -b -1`. **(T8)**

**✅ 8.4 a 8.6 cerrados el 2026-09-22.** Exposición **de `9.2 UNSAFE` a `3.1 OK`** con las 19 directivas de la
tanda 1 más `MemoryMax=1G`. El único `✗` que queda es `UMask=`, y está así **por decisión**: con `0027` los
archivos nacen 640 y systemd preferiría 0077; el grupo es `mudar` y hoy no hay nadie más dentro.

**Ninguno de los dos riesgos se materializó, y los dos se comprobaron explícitamente:**
- **Escritura bajo `ProtectSystem=strict`** — un login fallido dejó su línea en `/var/log/mudar/seguridad.log`:
  `2026-09-22 12:03:15,883 WARNING server.seguridad Login fallido usuario=usuario_que_no_existe ip=127.0.0.1`.
  **El `LogsDirectory` del 8.1 hizo innecesario el `ReadWritePaths`**, como se había previsto.
- **Resolución de nombres bajo `RestrictAddressFamilies`** — probada con la misma directiva puesta, en una
  unidad efímera: `systemd-run --uid=mudar --gid=mudar --wait --pipe --collect -p RestrictAddressFamilies="AF_INET AF_INET6 AF_UNIX AF_NETLINK" /opt/mudar/venv/bin/python3 -c 'import socket; print(socket.gethostbyname("smtp.office365.com"))'`
  → `40.99.202.114`, `status=0`. **`AF_NETLINK` bastaba**; el correo de avisos podrá resolver su servidor.

**Además, con el blindaje puesto:** la base de datos responde (el 401 del login sale tras consultar la tabla de
usuarios), sigue escuchando **solo** en `127.0.0.1:8000`, `journalctl -p err` no devuelve **ninguna** entrada, y
el registro de acceso mantiene la duración: `"POST /api/auth/login/ HTTP/1.1" 401 44 "-" "curl/8.5.0" 0.670935`.

**📌 Para el paso 13:** el `datepattern` del filtro de fail2ban tiene que reconocer `2026-09-22 12:03:15,883`
— con **coma** antes de los milisegundos, que es el formato de la biblioteca de registro de Python.

**✅ 8.7 cerrado — PASO 8 COMPLETO (2026-09-22).** Tras `wsl --shutdown` y volver a entrar, el servicio
**arrancó solo** (confirmado tres veces, PIDs 298, 303 y 304), con `Type=notify`, las 4 tareas y el
`MemoryMax` aplicado. **T8 cumplida: el diario es persistente** — 98 líneas conservando todos los arranques
del día a través de los apagados.
> ⚠️ **Dos artefactos de WSL que NO existirán en GTD, para no confundirlos con hallazgos:**
> - **`journalctl -b -1` devuelve «No entries»** aunque los datos estén ahí. No es pérdida de registro: el
>   reloj de la máquina **salta ~5 h** cuando WSL lo resincroniza con Windows, y eso descoloca el índice de
>   arranques. Se comprueba con `journalctl -u mudar-web --since today`, que sí los muestra todos.
> - **WSL reescribe `/etc/localtime` en cada arranque** con la zona de Windows. Se intentó fijarlo con
>   `[boot] command=…timedatectl set-timezone America/Bogota` en `/etc/wsl.conf` y **no funciona**: la zona
>   se queda en `Europe/Madrid`, o porque la orden no llega a ejecutarse o porque WSL la pisa después.
>   **La línea se retiró**, porque un remedio que no cura y parece que cura es peor que ninguno — mismo
>   criterio que con `ExecReload`. *(La errata inicial `America/BogotaX` falló de forma **muda**: WSL no
>   avisa de que el comando de arranque fracasó.)*

**🔴 REQUISITO PREVIO DEL PASO 11, que nace de lo anterior:** antes de probar `mudar-cronometros.timer` hay que
ejecutar `sudo timedatectl set-timezone America/Bogota` en la sesión, porque **los temporizadores de systemd
usan la zona del sistema operativo**. Sin eso, el `OnCalendar=…21:00:00` dispararía a las 14:00 de Bogotá y la
prueba sería falsa sin avisar. **Y allí se decide la solución duradera:** escribir la zona dentro del propio
temporizador —`OnCalendar=*-*-* 00,05,21:00:00 America/Bogota`—, que resolvería el ensayo **y** blindaría la
producción contra un cambio de zona en el servidor.

**🔴 VERIFICACIÓN PARA EL BLOQUE D:** confirmar con `timedatectl` que el servidor de GTD está en
`America/Bogota` antes del paso del temporizador. Cuesta cinco segundos y cubre que la máquina llegue en UTC.

**Los dos riesgos del paso, y dónde se verán:** `ProtectSystem=strict` bloqueando una escritura no declarada
(síntoma: `Permission denied` en una línea de Python, visible en el login del 8.6) y `RestrictAddressFamilies`
rompiendo la resolución de nombres (por eso la prueba de resolución es explícita). Salida en ambos casos:
volver a la unidad del 8.3, que está en git.

**Verificación**
- La unidad declara `Environment=PYTHONUNBUFFERED=1` y, tras arrancar, `journalctl -u` muestra líneas de Gunicorn. **(T9)**
- `systemctl show -p Environment` (o el entorno del proceso) da los valores exactos, sin comillas ni cortes. **(T10)**
- `systemctl cat` muestra `--workers` y `--timeout` explícitos. **(T4)**
- `curl -i -H "Host: <dominio del entorno>" http://127.0.0.1:8000/api/auth/perfil/` responde 401 desde Django, sin pasar por Nginx. El `-H` es obligatorio: sin él, curl envía `Host: 127.0.0.1:8000`, que no está en `ALLOWED_HOSTS`, y da 400 aunque todo esté bien (la misma familia que T1).
- Después de `wsl --shutdown` y volver a entrar, `journalctl -b -1` muestra el arranque anterior. **(T8)**

## 9. Frontend compilado ✅

**Cerrado el 2026-09-22.** Seis subpasos. El frontend se compila en Windows y al servidor sube solo el `dist/`.

### 9.1 — Corregir `index.html`: favicon, título e idioma
Tres defectos, los tres incrustados en el `dist/` al compilar, así que se arreglan a la vez o no se arreglan hasta la siguiente compilación: el icono era el de Vite, el título de la pestaña decía literalmente `client`, y `<html lang="en">` en una aplicación en español.
- `client/public/logoMudar.png` — **256×256, cuadrado, 19 KB, con transparencia**. Generado a partir del logo en alta resolución que aportó Angel (1786×1456) con las bibliotecas de imagen de Windows vía PowerShell y `System.Drawing`: en esta máquina no hay PIL ni ImageMagick. El logo original **no es cuadrado** (1,23:1), así que se centra sobre lienzo cuadrado con relleno transparente, sin deformarlo.
- `<link rel="icon" type="image/png" href="/logoMudar.png" />` · `<title>Mudar de Colombia</title>` · `lang="es"`.
- `client/public/vite.svg` **borrado**, sin referencias sueltas en el proyecto.

### 9.2 — Crear `client/.env.production` con la URL del despliegue
**Decisión de fondo: Nginx sirve el frontend y la API desde el MISMO origen** — el `dist/` en `/` y `/api/` reenviado a Gunicorn. Con eso el navegador nunca habla con dos orígenes y **CORS deja de intervenir**.
- Se usa `.env.production` y **no se toca `client/.env`**: Vite carga `.env` en todos los modos y este encima solo al compilar, así que `npm run dev` sigue apuntando a `localhost:8000` y el desarrollo no se rompe.
- Ensayo `http://localhost` (Nginx en el 80) · producción `https://app.mudarcolombia.com`.
- Está **fuera de git** (`.gitignore` lo cubre con `.env.*`), así que hay que crearlo a mano en cada máquina donde se compile. El mecanismo se documentó en `client/.env.example`, que sí está en git — sin esa nota, quien clone el repositorio vería `localhost:8000` y no sabría que al compilar se usa otro archivo.
- Se eliminaron `VITE_APP_NAME` y `VITE_APP_VERSION`: **ninguna parte del código las leía**.

### 9.3 — Compilar el frontend
`npm ci` y `npm run build`, con **Node v24.5.0 y npm 11.5.1**. 147 módulos, 3,12 s, **517 KB** en cinco archivos.
- **`npm ci` y no `npm install`**: reinstala exactamente lo del `package-lock.json`, mientras que `install` puede traer versiones distintas porque `package.json` declara rangos con acento circunflejo.
- ⚠️ **Tropiezo:** el primer `npm ci` murió con `EPERM` al no poder borrar `lightningcss.win32-x64-msvc.node`, **bloqueado por un servidor de desarrollo de Vite abierto desde el día anterior**. Dejó `node_modules` a medio borrar (17 paquetes de 272). Se resolvió cerrando Vite y repitiendo. **En Windows, cerrar `npm run dev` antes de `npm ci`.**

> **🔒 Auditoría de dependencias, resuelta antes de compilar.** `npm ci` reportó **14 vulnerabilidades**; solo **4 llegan al navegador** y las otras 10 viven en herramientas de compilación que no viajan en el `dist/`. Se actualizaron las dos de producción: **axios 1.16.1 → 1.20.0** y **react-router-dom 7.15.1 → 7.18.4**. `npm audit --omit=dev` pasó a **0 vulnerabilidades**. Las 10 de desarrollo se dejan: actualizar `vite` o `eslint` a días del despliegue mueve la compilación entera para protegerse de algo que ningún usuario ejecuta.
> *Análisis previo: de las 5 alertas del enrutador, 3 eran de RSC/SSR (inaplicables, la aplicación es cliente puro), 1 era denegación de servicio en el navegador del propio visitante, y la de redirección abierta exigía un destino de navegación controlado por el usuario — verificado que hay **cero** llamadas a `navigate()` y que los 21 enlaces apuntan a cadenas fijas. Se actualizó igualmente porque «no explotable hoy» depende de cómo está escrito el frontend hoy, y porque era el último momento barato.*

> **🧪 Prueba de humo en desarrollo, intercalada antes de compilar.** Se probó `npm run dev` en el navegador para separar una posible regresión del enrutador de los fallos de Nginx del paso 10 — mismo principio de capas que con Gunicorn. **Los 8 puntos pasaron**: login con dos roles, navegación por menú, entrada directa por URL, parámetros de consulta, historial adelante/atrás, y la expulsión por sesión caducada (que prueba el interceptor de axios). Sin errores en consola.
> ⚠️ **Choque de puertos, artefacto de WSL:** el reenvío de puertos de WSL se pone **por delante** de los procesos de Windows en el loopback, así que con `mudar-web` corriendo, `localhost:8000` llegaba al Gunicorn del ensayo (301 con `DEBUG=False`) en vez de al `runserver` de desarrollo. Se resuelve parando el servicio del ensayo durante la prueba. En GTD no existe, porque no hay dos sistemas compartiendo un loopback.
> **Dos hallazgos de producto que salieron de ahí:** el título de la pestaña, y que **«Desactivar DOM» apuntaba a `/doms?accion=desactivar` sin que NADIE lea ese parámetro** — ningún `useSearchParams` del frontend lo consulta, así que la ruta era idéntica a `/doms`. Se ocultó la entrada con `MOSTRAR_DESACTIVAR_DOM = false` (`Layout.jsx`), mismo criterio que con informes: se oculta la entrada, la ruta y los archivos siguen en su sitio, la limpieza queda pendiente.

### 9.4 — Verificar la URL incrustada (T14)

> ⚠️ **SUPERADO el 2026-09-23, en el subpaso 10.7.2.** `VITE_API_URL` pasó a ir **vacía**: axios emite
> rutas relativas y el paquete ya no lleva ningún dominio dentro. El **mismo `dist/` sirve para el ensayo
> y para GTD**, así que desaparece la compilación por entorno. Lo de abajo describe la compilación del
> 22-sep y se conserva como historia.

**La comprobación vigente es esta:**
```
grep -o 'baseURL:"[^"]*"' dist/assets/*.js      →  baseURL:""
```
- ⚠️ **Ya NO vale buscar `localhost` en el paquete: da falsos positivos.** axios y React Router llevan
  `http://localhost` escrito dentro como **base de pega** para poder construir `new URL(ruta_relativa, base)`,
  y la pisan con `window.location.origin` en cuanto hay navegador. Buscarlo devuelve tres coincidencias que
  no tienen nada que ver con nuestra configuración.
- Lo que se comprueba es `baseURL`, que es lo único que sale de `.env.production`. Debe salir **vacío**.

**Historia — compilación del 2026-09-22:**
- `http://localhost` **está** dentro de `dist/assets/*.js`: el `.env.production` funcionó.
- `localhost:8000` aparece **cero veces** en el JS y en el HTML.
- Las demás URL absolutas del paquete son enlaces de documentación de las librerías (`react.dev`, `reactrouter.com`, `github.com`), que salen en sus mensajes de error.
- ⚠️ **La verificación no es opcional:** había un `dist/` de agosto compilado con `localhost:8000`. Se borró antes de compilar para que no quedara duda de qué era nuevo y qué residuo.

### 9.5 — Copiar el `dist/` al sistema de archivos de Linux
```
sudo mkdir -p /var/www/mudar
sudo cp -rT /mnt/c/Users/angel/Desktop/Mudar/client/dist /var/www/mudar
sudo chown -R root:root /var/www/mudar
sudo find /var/www/mudar -type d -exec chmod 755 {} +
sudo find /var/www/mudar -type f -exec chmod 644 {} +
```
- **`-T` en el `cp`**: sin él, como el destino ya existe, crearía `/var/www/mudar/dist` en vez de volcar el contenido.
- ⚠️ **Dos `chmod` con `find`, y NO un `chmod -R u=rwX,go=rX`.** La `X` mayúscula aplica el bit de ejecución a los directorios **o a lo que ya lo tenga**, y todo lo que viene de `/mnt/c` llega como **777** porque WSL inventa los permisos. Verificado en la copia: los archivos aterrizaron en 755. Con la `X` se habrían quedado así en vez de bajar a 644.
- El `chown` resultó **no cambiar nada** (al copiar con `sudo`, los archivos ya nacen de `root`), pero se mantiene: garantiza el estado en vez de suponerlo.
- **Resuelve la fricción `www-data` ↔ `mudar` que quedó pendiente de este bloque.** `www-data` lee por caer en la clase «los demás», **sin aparecer en ningún comando**, así que no hace falta meterlo en el grupo `mudar` — que además le habría abierto `/var/log/mudar`, donde `seguridad.log` lleva direcciones IP. El `dist/` es contenido público: cualquier navegador se lo descarga entero.

### 9.6 — Verificar T12 y el recorrido de permisos
- **T12:** `df` confirma que `/var/www/mudar` está en `/dev/sdd` montado en `/`, el sistema de archivos propio de Linux, no en el puente de `/mnt/c`.
- **`namei -l /var/www/mudar/index.html`** muestra la cadena entera desde la raíz: los cuatro directorios en `drwxr-xr-x` y el archivo en `-rw-r--r--`. `www-data` puede atravesar los cuatro y leer el archivo. **El eslabón que falla suele ser un directorio intermedio, no el archivo** — es la causa del 403 del `dist/`.
- Estado final: directorios **755**, archivos **644**, todo `root:root`.

**🔴 REGLA PARA EL BLOQUE D, nacida aquí: primero se commitea, después se compila.** El `dist/` del ensayo se compiló desde un árbol con cambios sin guardar, así que **no corresponde a ningún commit**. En el ensayo da igual; en producción no, porque la **sexta pieza del respaldo** exige guardar el `dist/` junto al `git rev-parse HEAD` del código del que salió. Compilar sin commitear anula esa pieza.

**No se puede probar que el frontend se sirva hasta el paso 10**, porque Nginx todavía no existe.

## 10. Nginx ✅

**Decisiones tomadas el 2026-09-23, antes de teclear nada. Las tres son del ENSAYO y no viajan a GTD.**

1. **El 301 de `SECURE_SSL_REDIRECT`.** Con `DEBUG=False` Django responde 301 a toda petición que no traiga `X-Forwarded-Proto: https`. Opciones: que Nginx mienta enviando esa cabecera fija por el puerto 80, o montar un certificado autofirmado. **Se eligió el certificado**, porque la cabecera que viaja a GTD es `$scheme` y la otra opción dejaría sin ensayar justo la línea que cambia (objeción C2 del plan).
2. **Nombre propio en vez de `localhost`.** HSTS se aplica **por host e ignora el puerto**: con `localhost`, el `max-age=3600` que envía Django habría forzado HTTPS durante una hora en *todos* los puertos de localhost, rompiendo el Vite de desarrollo (5173) y el `runserver` (8000). Se usa **`app.mudar.test`**; el TLD `.test` está reservado por la IETF para esto.
3. **Los estáticos del panel van a Gunicorn, no al disco.** WhiteNoise los sirve desde dentro del proceso. La alternativa —que Nginx los leyera de `/opt/mudar/staticfiles`— exigiría meter a `www-data` dentro de `/opt/mudar`, donde viven el código y el venv. El panel lo usan dos o tres personas muy de vez en cuando: el salto de proxy no cuesta nada medible.

### 10.1 — El nombre

En **Windows**, PowerShell como administrador:
```powershell
Add-Content -Path "$env:SystemRoot\System32\drivers\etc\hosts" -Value "127.0.0.1 app.mudar.test" -Encoding ascii
```
⚠️ **`-Encoding ascii` explícito.** Si se escribe en UTF-16 —lo que hacen `Out-File` y `>` por omisión en PowerShell 5.1— Windows deja de resolver **todos** los nombres del archivo, no solo el nuevo, y sin ningún aviso.

En **WSL**:
```
sudo cp -p /etc/mudar/env /etc/mudar/env.bak
sudo sed -i 's|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=app.mudar.test,localhost,127.0.0.1|' /etc/mudar/env
sudo sed -i 's|^CSRF_TRUSTED_ORIGINS=.*|CSRF_TRUSTED_ORIGINS=https://app.mudar.test|' /etc/mudar/env
sudo systemctl restart mudar-web && systemctl is-active mudar-web
```
- **`cp -p`**, no `cp` a secas: sin `-p` la copia nace con la máscara de root (644) y los secretos quedarían legibles por cualquier usuario de la máquina.
- **El separador de `sed` es `|` y no `/`**, porque el segundo valor lleva `https://` dentro.
- **`ALLOWED_HOSTS` conserva `localhost` y `127.0.0.1`** para poder llamar a Gunicorn directamente con `curl` en la verificación por capas del 10.3. Django compara sin el puerto.
- **`restart` y no `reload`:** `EnvironmentFile` lo lee systemd al arrancar la unidad; el archivo puede cambiar mil veces que el proceso no se entera.

**Verificación**
- `ping app.mudar.test` desde Windows responde desde `127.0.0.1`.
- `sudo grep -E '^(DEBUG|ALLOWED_HOSTS|CSRF_TRUSTED_ORIGINS)=' /etc/mudar/env` — se pide **solo lo que se va a mirar**: un `cat` dejaría la `SECRET_KEY` y la contraseña de la base en el historial de la terminal.

> **Dos filtros por nombre en dos capas, y se confunden constantemente.** `server_name` es de Nginx y decide *qué bloque responde*. `ALLOWED_HOSTS` es de Django y decide *si acepta* la cabecera `Host`; si no coincide, responde `400 DisallowedHost`. Ninguno le pregunta al otro.

### 10.2 — Instalar Nginx

```
sudo apt update && sudo apt install -y nginx
```
> **En Debian y Ubuntu, instalar un servidor lo deja ARRANCADO.** Es política de la distribución: el paquete habilita el servicio y lo levanta. En cuanto termina el comando, el puerto 80 ya está ocupado y la página de bienvenida se puede pedir.

**Verificación**
- Antes de empezar, que el 80 esté libre: `ss -lnt` y `command -v apache2`.
- `systemctl is-active nginx` → `active`; `curl -I http://localhost` → 200 con `Server: nginx`.
- **`http://app.mudar.test` en el navegador de Windows muestra «Welcome to nginx!»** — primer recorrido completo del ensayo: nombre resuelto en Windows, reenvío de puertos de WSL, servicio y puerto.

### 10.3 — Bloque mínimo en el 80

**El orden 10.3 → 10.4 → 10.5 está forzado:** `nginx -t` falla si `ssl_certificate` apunta a un archivo que no existe, así que no se puede instalar la configuración final antes de generar el certificado. Se aprovecha para verificar por capas.

```
echo "127.0.0.1 app.mudar.test" | sudo tee -a /etc/hosts
```
Es el **segundo** resolvedor: WSL y Windows tienen el suyo y no se consultan entre sí. Hace falta para poder probar con `curl` desde dentro de la máquina.

Después, una configuración provisional con un solo `server` en el 80 que reenvíe todo a `http://127.0.0.1:8000`, con `Host $host`, `X-Forwarded-For $remote_addr`, `X-Forwarded-Proto $scheme` y `proxy_read_timeout 35s`. Se activa así:
```
sudo rm /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/mudar /etc/nginx/sites-enabled/mudar
sudo nginx -t && sudo systemctl reload nginx
```
- **Hay que quitar el `default`**, que trae `listen 80 default_server` y atendería cualquier `Host` que no case con otro bloque: un despiste con el nombre devolvería la página de bienvenida en vez de un error, y estarías depurando una configuración que ni se lee.
- **Borrar un enlace simbólico no borra su destino.** El `default` real sigue en `sites-available` con sus 2.412 bytes; reactivarlo es un `ln -s`. Por eso existe el esquema de dos carpetas.

**Verificación — y el éxito es un 301**
```
curl -I http://app.mudar.test/      →  301  Location: https://app.mudar.test/
```
Ese `Location` prueba cuatro cosas a la vez: Nginx hizo casar el `server_name`, reenvió a Gunicorn, **Django aceptó el `Host`** (no hay 400) y **el destino dice `app.mudar.test` y no `127.0.0.1:8000`**, que es la prueba de que `proxy_set_header Host $host` funciona. **Trampa T1 cerrada sin provocarla.**

### 10.4 — Certificado autofirmado

```
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/mudar-ensayo.key \
  -out /etc/ssl/certs/mudar-ensayo.crt \
  -subj "/CN=app.mudar.test" \
  -addext "subjectAltName=DNS:app.mudar.test"
```
- **`-nodes`** = sin cifrar la clave. Cifrada, Nginx pediría la contraseña en cada arranque y el servicio no podría levantarse solo.
- **`-addext subjectAltName` es imprescindible.** Los navegadores **ignoran el `CN`** desde hace años y validan el nombre solo contra ese campo. Un certificado con solo `CN` da error de nombre.
- Los puntos y los `+` que imprime son el buscador de primos de OpenSSL. No significan nada.

**Verificación**
```
openssl x509 -in /etc/ssl/certs/mudar-ensayo.crt -noout -subject -dates -ext subjectAltName
```
Debe mostrar `DNS:app.mudar.test`. El directorio `/etc/ssl/private` es `drwx--x---`: el grupo `ssl-cert` tiene solo `x`, así que puede abrir la clave si sabe el nombre pero **no listar** el directorio.

> **Autofirmado no es débil, es no avalado.** El cifrado es idéntico al de Let's Encrypt —se midió `TLSv1.3 / TLS_AES_256_GCM_SHA384 / X25519`—; lo que falta es la cadena de confianza. El aviso del navegador **no desaparecerá nunca** aquí: `.test` está reservado y ninguna autoridad puede firmarlo.

### 10.5 — Los dos bloques definitivos

La configuración pasa a vivir en **`despliegue/nginx-mudar.conf`**, versionada, y se instala con:
```
sudo install -o root -g root -m 644 \
  /mnt/c/Users/angel/Desktop/Mudar/despliegue/nginx-mudar.conf \
  /etc/nginx/sites-available/mudar
sudo nginx -t && sudo systemctl reload nginx
```
⚠️ **Desde el 12.7.4 el sitio depende de un segundo archivo**, `nginx-cabeceras.conf` → `/etc/nginx/snippets/mudar-cabeceras.conf`, que se instala **antes**. Ver 12.7.

⚠️ **`install` y no `cp`:** fija dueño, grupo y permisos en la misma operación, sin heredar los que WSL inventa en `/mnt/c`. **Trampa T12.** En GTD el origen será otro —`scp` o el repositorio clonado—; el destino es idéntico.

⚠️ **Se abandonó el método del *heredoc*.** Pegar 26 líneas de `sudo tee << 'EOF'` en la terminal se cortó a la mitad y dejó la shell en el prompt `>`. No se escribió nada —bash lee el heredoc entero antes de ejecutar el comando— pero el ciclo «editar el archivo versionado e instalarlo» es más seguro, reproducible y deja el artefacto listo para el commit.

⚠️ **`listen 443 ssl http2;` y NO `http2 on;`.** La directiva suelta llegó en Nginx 1.25.1 y Ubuntu 24.04 trae la **1.24.0**, así que la forma nueva hace fallar `nginx -t`. Casi toda la documentación reciente de internet usa ya la nueva. En GTD será el mismo 1.24.0.

**Verificación**
```
curl -I  http://app.mudar.test/                    →  301 de Nginx (Content-Length 178)
curl -kI https://app.mudar.test/api/auth/perfil/   →  HTTP/2 401
```
El **401 y no 301** es el cierre del paso: Django vio `X-Forwarded-Proto: https` y dejó de redirigir. La cabecera `www-authenticate: Token` la escribe `ExpiringTokenAuthentication`, así que la petición recorrió toda la cadena. Aparece también `strict-transport-security: max-age=3600`: **HSTS se activa aquí**, y es la razón de haber elegido un nombre propio en el 10.1.

### 10.6 — Los estáticos del panel

Se añade `location /static/ { proxy_pass http://127.0.0.1:8000; }` y se instala igual que el 10.5.

> **Este subpaso no arregla nada que esté roto: asegura algo que el 10.7 rompería.** Hoy los estáticos funcionan *por accidente*, porque `location /` se lleva absolutamente todo. En cuanto la raíz pase a servir el frontend desde el disco, dejarían de llegar a Gunicorn y el panel saldría **sin estilos**: un documento en blanco con enlaces azules. Lo confuso del síntoma es que la aplicación de React se vería perfecta, porque la sirve otro bloque.

**Verificación previa, que cierra una incógnita del 7.6:** `collectstatic` corrió **como root** y Gunicorn corre como `mudar`. Se comprueba **antes** de tocar nada, aprovechando que todo va a Gunicorn:
```
curl -sk -o /dev/null -w '%{http_code} %{content_type} %{size_download}\n' \
  https://app.mudar.test/static/admin/css/base.css     →  200 text/css 22120
```
Sale bien: el recorrido de permisos da y no hay nada que arreglar.

> **Herencia de directivas.** `proxy_set_header` y `proxy_read_timeout` se declaran **una sola vez a nivel de `server`** y todos los `location` las heredan; solo `proxy_pass` va dentro de cada uno. ⚠️ La herencia es **por directiva completa**: si un `location` declarase su propio `proxy_set_header`, perdería **las tres**, no solo la que repita. El síntoma sería un 400 o un bucle de redirecciones en esa ruta y solo en esa.

### 10.7 — El frontend

**10.7.1 — El prefijo del panel.**
```
sudo sed -i 's|^ADMIN_URL=.*|ADMIN_URL=gestion/panel-ensayo/|' /etc/mudar/env
sudo systemctl restart mudar-web && systemctl is-active mudar-web
```
**Por qué se parte la ruta en prefijo fijo + parte secreta.** En cuanto la raíz deja de reenviar, solo llega a Django lo que tenga su propio `location`, y el panel es uno de ellos. O Nginx conoce la ruta **completa** —y entonces el valor no adivinable de producción habría que escribirlo también en la configuración de Nginx, en dos archivos que no se conocen y con valores distintos por entorno—, o conoce solo un **prefijo estable**. Con `location /gestion/`, la configuración de Nginx queda idéntica en ensayo y en GTD, y el secreto no sale de `/etc/mudar/env`.
- En GTD: `ADMIN_URL=gestion/<parte-secreta>/`, generada con `openssl rand -hex 6`. Sin barra inicial, con barra final. **No se reutiliza el valor del ensayo.**
- Pedir `/gestion/` a secas da 404: Django no tiene esa ruta. Se sabe que el prefijo existe; no qué hay debajo. `ADMIN_URL` es una capa de estorbo, no un control de acceso.

**10.7.2 — Recompilar el frontend**, en Windows, con `VITE_API_URL=` **vacía** en `client/.env.production`. Ver **9.4** para la comprobación vigente (`baseURL:""`).

**10.7.3 — Copiar el `dist/`.** Igual que en 9.5, **con un añadido**: hay que vaciar el destino primero, porque Vite pone una huella del contenido en el nombre de cada archivo y un `cp` copia encima pero **no borra** lo que ya no existe en el origen. Los assets viejos se acumularían en cada compilación e impedirían responder a «¿qué versión se está sirviendo?».
```
sudo rm -rf /var/www/mudar && sudo mkdir -p /var/www/mudar \
 && sudo cp -rT /mnt/c/Users/angel/Desktop/Mudar/client/dist /var/www/mudar \
 && sudo chown -R root:root /var/www/mudar \
 && sudo find /var/www/mudar -type d -exec chmod 755 {} + \
 && sudo find /var/www/mudar -type f -exec chmod 644 {} +
```
⚠️ **Encadenar con `&&`.** Con saltos de línea, si el `cp` fallara los `chmod` correrían sobre un directorio vacío **sin dar error**, y tendrías un sitio vacío sin ninguna señal.

⚠️ **`sudo rm -rf` no tiene papelera.** Lo peligroso no es el comando sino **un espacio de más**: `rm -rf / var/www/mudar` intenta borrar la raíz. Leer la ruta entera antes de pulsar Enter.

**Verificación:** un `md5sum` de los cinco archivos en origen y destino debe coincidir. Es la comprobación que conviene usar **siempre que un archivo cruce de Windows a Linux** —y en GTD, cuando el `dist/` suba por `scp`—: prueba de una vez que no hubo truncado, conversión de finales de línea ni cambio de codificación. Los archivos llegan de `/mnt/c` como **755**, con el bit de ejecución puesto; los dos `find` lo quitan.

**10.7.4 — La configuración con `try_files`.** Se instala como en el 10.5. Añade `root /var/www/mudar`, los tres `location` que van a Django (`/api/`, `/static/`, `/gestion/`), las dos reglas de caché y:
```nginx
location / { try_files $uri $uri/ /index.html; }
```
> **Nginx elige el `location` por el prefijo MÁS LARGO que case, no por el orden del archivo.** Una petición a `/api/doms/` casa con `/api/` y con `/`, y gana `/api/`. Podrías barajar los bloques y el resultado sería idéntico. La excepción es `=`, coincidencia exacta, que gana a todos.

**Caché: `assets/` un año, `index.html` nunca.** Los assets llevan huella en el nombre, así que su URL cambia si cambia el código y se pueden cachear para siempre. `index.html` es el **único nombre fijo**: si el navegador se quedara con una copia vieja, seguiría pidiendo los assets anteriores aunque el despliegue ya hubiera cambiado.

**10.7.5 — Verificación**
```
/              →  200  text/html  478 bytes
/doms/57       →  200  text/html  478 bytes      ← el try_files, en una línea
/assets/....js →  200  cache-control: public, max-age=31536000, immutable
/logoMudar.png →  200  image/png                 ← el favicono deja de dar 404
api perfil 401 · static 200 · panel 302          ← lo que va a Django sigue yendo
```
`/doms/57` no existe en el disco y devuelve **los mismos 478 bytes** que la raíz, o sea el mismo `index.html`. Entrar por URL directa o pulsar F5 en una pantalla interna ya no da 404.

⚠️ La ruta vieja del panel pasa a devolver **200**: ya no es Django, es **la SPA atrapándola** con el `try_files`. Inofensivo y esperado.

### 10.8 — El límite de peticiones al login

```nginx
limit_req_zone $binary_remote_addr zone=login:10m rate=10r/m;   # contexto http, arriba del archivo

location = /api/auth/login/ {
    limit_req zone=login burst=10 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8000;
}
```
- **`zone=login:10m` son 10 MEGABYTES de memoria compartida, no 10 minutos.** Dan para unas 160.000 IPs. El tiempo va en `rate`.
- **El `http` de Nginx no es el protocolo**, es el bloque que contiene *toda* la configuración web, cifrada o no. **No existe ningún bloque `https`.** Nuestro archivo se incluye dentro de `http`, así que esta posición es la correcta.
- **La ruta es `/api/auth/login/`** (`server/urls.py:86`). El `/api/login/` de `CLAUDE.md` **no existe**: si se copia mal, el límite se aplica a una ruta fantasma y nadie se entera.
- **`=` es coincidencia exacta.** Sin él, la ruta casaría con `/api/` y no se limitaría nada.
- **`limit_req_status 429`** porque el valor por omisión es **503**, que miente: dice «servidor no disponible» y tanto una persona como un monitor lo leerían como una caída.

> **El número es GENEROSO a propósito, y el reparto es contrario a la intuición.** En la planta todos los equipos salen por **una sola IP pública**, así que comparten cubo y un cambio de turno son cinco ingresos casi simultáneos — es la objeción que archivó el tope de intentos fallidos (8.4.1). Y sobre todo: si Nginx rechaza aquí, **la petición no llega a Django**, no se escribe la línea en `seguridad.log` y **`fail2ban` se queda ciego**. Apretar este cerrojo estropea al que de verdad distingue un intento fallido de uno bueno. **`limit_req` generoso, `fail2ban` estricto.**

**Verificación medida (2026-09-23)** — 16 POST seguidos:
```
1-11  → 401      pasan: 1 del rate + 10 del burst
12-16 → 429
tras 12 s: 401, 401, 429        ← 2 plazas recuperadas, una cada 6 s
16 GET a /api/auth/perfil/ → 401 x16, ningún 429   ← el `=` aisló la ruta
sudo grep -c 'usuario=x ' /var/log/mudar/seguridad.log → 13
```
Los **13** son las que llegaron a Django. Las cinco con 429 **no dejaron línea**: el reparto con `fail2ban` queda probado con datos, no con argumentos.

> 🪤 **HALLAZGO DEL 10.8, y rompe el paso 13 en silencio.** El registro decía `11:37` mientras el sistema decía `19:07`: siete horas. No es un error — **Django escribe sus registros en `America/Bogota`** porque `TIME_ZONE` lo fija al arrancar, mientras el sistema operativo estaba en `Europe/Madrid`. `fail2ban` lee `seguridad.log` y compara la fecha **con el reloj del sistema**: con esa diferencia, todas las líneas le parecerían viejísimas, caerían fuera de su ventana de vigilancia y **no banearía a nadie jamás**, sin error ni aviso. Se cierra alineando el sistema: `sudo timedatectl set-timezone America/Bogota`. **Comprobar la zona antes del paso 11 y del 13.** En GTD, un servidor entregado en UTC reproduce esto idéntico.

### 10.9 — La excepción de ACME

```
sudo mkdir -p /var/www/certbot/.well-known/acme-challenge
```
```nginx
location ^~ /.well-known/acme-challenge/ {
    root /var/www/certbot;
    default_type "text/plain";
}
location / { return 301 https://$host$request_uri; }
```
El `return 301` pasa de estar a nivel de `server` a estar **dentro de `location /`**, o se tragaría el desafío.
- **`^~`** = «si el prefijo casa, no sigas buscando». Con solo estos dos `location` bastaría el prefijo más largo, pero lo deja explícito y protege de una regla con expresión regular futura.
- **`default_type text/plain`** porque el archivo del desafío **no tiene extensión** y Nginx lo serviría como binario.
- ⚠️ **No es solo para la emisión: la renovación usa este mismo camino.** Si queda mal, funciona 90 días y luego el certificado vence de madrugada, sin aviso útil y con el HSTS impidiendo entrar en claro a mirar qué pasa.

**Verificación en WSL, parcial pero suficiente.** Se comprueba **el buzón, no el cartero**: `.test` no lo puede validar ninguna autoridad, así que se pone una ficha falsa a mano.
```
echo "prueba-acme-10.9" | sudo tee /var/www/certbot/.well-known/acme-challenge/prueba > /dev/null
curl -i http://app.mudar.test/.well-known/acme-challenge/prueba
```
→ `200 OK`, `Content-Type: text/plain`, **sin 301**. Y hay que comprobar que el resto del 80 **sigue redirigiendo**: `/`, `/doms/57` y `/api/doms/` deben dar 301 conservando la ruta.

> **En qué consiste el desafío.** `certbot` pide el certificado, Let's Encrypt responde con una ficha aleatoria, `certbot` escribe un archivo cuyo **nombre es la ficha** y cuyo **contenido es la ficha, un punto y la huella SHA-256 de la clave pública de tu cuenta**, y Let's Encrypt pide esa URL **desde internet y por el puerto 80 en claro**. La segunda mitad del contenido es imprescindible: si bastara la ficha, cualquiera que la interceptara —viaja en claro— podría obtener un certificado de tu dominio.

### 10.10 — Batería de verificación

Con todo instalado, las diez comprobaciones. **Siempre por capas: Gunicorn en `127.0.0.1:8000` primero y Nginx después.**
- `/api/auth/perfil/` a través de Nginx responde **401**, no 400. **(T1)**
- `/static/admin/css/base.css` responde **200** con `Content-Type: text/css`. **(T2)**
- El desafío de ACME por el 80 devuelve su contenido, no `index.html`, y **sin 301**. **(T3, parcial en WSL)**
- `proxy_read_timeout` (**35 s**) ≥ `--timeout` de Gunicorn (**30 s**). **(T4)** ⚠️ Al comprobarlo con `grep`, `mudar-web.service` menciona `--timeout` **tres veces** —dos en comentarios—; hay que quedarse con la línea real o la comparación numérica falla.
- Una ruta de la SPA, `/doms/57`, devuelve `index.html` con el mismo tamaño que la raíz.
- El login responde **429** al superar el límite.
- El puerto 80 redirige todo lo demás con **301**.
- El panel en `/gestion/...` responde **302** hacia su login.
- Los assets llevan `Cache-Control: public, max-age=31536000, immutable`, **una sola cabecera**.
- `nginx`, `mudar-web` y `postgresql` activos; **80 y 443 en `0.0.0.0`, 8000 y 5432 solo en `127.0.0.1`**.

**Calibración de errores, para no confundir una respuesta negativa con una avería.** Las herramientas del navegador pintan en rojo todo estado ≥ 400, y eso incluye respuestas legítimas:
- **404** — llegó a Django y no hay nada en esa ruta. *La cadena funciona.*
- **400** — llegó a Django y rechazó el `Host`. *Fallo de `ALLOWED_HOSTS`.* ⚠️ Desde el 12.7 un `Host` ajeno ya no llega a Django: lo corta Nginx sin responder. Un 400 por `Host` indica ahora que el nombre **sí** está en `server_name` y **no** en `ALLOWED_HOSTS`: las dos listas divergen.
- **502** — Nginx no obtuvo respuesta de Gunicorn. *Servicio caído o `proxy_pass` mal.*
- **Conexión rechazada** — nadie escucha en ese puerto. *Nginx caído.*
- **Demasiadas redirecciones** — falta `X-Forwarded-Proto`.

**Si la cadena estuviera rota no habría código de estado ninguno**: verías conexión rechazada, reinicio de conexión o tiempo agotado. Que exista un número ya prueba que los dos extremos hablaron.

## 11. Temporizador de cronómetros ✅

**Objetivo:** que el cierre de cronómetros olvidados deje de depender de que alguien abra la aplicación. Hoy solo barre cuando una persona navega y el frontend pide los avisos; con el temporizador lo dispara el sistema a las 21:00, 00:00 y 05:00, aunque no haya nadie delante. Cubre noches, fines de semana y festivos.

**Lo que este paso verifica es la FONTANERÍA, no la lógica de negocio:** que la unidad arranca, corre como el usuario correcto, recibe las credenciales y deja rastro en el diario. Qué cerrar y con qué `fin` ya tiene su propia suite de pruebas, y en el ensayo las doce tablas de operación están vacías, así que el barrido encuentra cero.

**Son tres eslabones y conviene no confundirlos:**
```
.timer   →  a las 21:00 activa...
.service →  ...que ejecuta, como el usuario mudar y con las credenciales...
.py      →  ...server/management/commands/cerrar_cronometros.py, que hace el trabajo
```
Las dos unidades son configuración declarativa, sin lógica. El código es el tercero.

> 🔴 **REQUISITO PREVIO, viene del 10.8.** Comprobar con `timedatectl` que el sistema operativo está en `America/Bogota` **antes** de interpretar ningún horario. Los temporizadores de systemd usan la zona del sistema, no la de Django. En WSL hay que reaplicarlo tras cada arranque si Windows no está también en esa zona; en GTD se fija una vez en el paso 3.
>
> ⚠️ **Con el sistema en otra zona, el barrido de las 21:00 caería en mitad del turno de tarde**, cerrando cronómetros vivos. Es el fallo más caro de este paso y no da ningún error.

### 11.0 — El defecto que traía la unidad

`mudar-cronometros.service`, escrito el 2026-09-16, **no declaraba `EnvironmentFile`**. Habría muerto en el primer disparo, a las 21:00, sin nadie delante:
- `/opt/mudar` **no tiene ningún `.env`** —solo `.env.example`—, así que `python-decouple` no tiene de dónde leer.
- `settings.py` hace **20 llamadas a `config()`**, y `SECRET_KEY` y las credenciales de la base **no tienen valor por omisión**: Django lanza `UndefinedValueError` al importar.
- El comentario del `WorkingDirectory` decía que estaba ahí porque «python-decouple busca el `.env` desde él». **Describía un mecanismo que no existe en esta máquina** — misma familia del 8.3.4 de `CLAUDE.md`: un comentario que fabrica documentación falsa.

Se añadieron tres directivas, todas copiadas de `mudar-web.service` para que las dos unidades no diverjan:
```ini
EnvironmentFile=/etc/mudar/env       # sin ella el comando muere al importar Django
Environment=PYTHONUNBUFFERED=1       # T9: sin ella el diario parece vacío
LogsDirectory=mudar                  # garantiza /var/log/mudar aunque mudar-web
LogsDirectoryMode=0750               # no haya arrancado nunca; mismo modo que allí
```

### 11.1 — Instalar las dos unidades

```
sudo install -o root -g root -m 644 \
  /mnt/c/Users/angel/Desktop/Mudar/despliegue/mudar-cronometros.service \
  /mnt/c/Users/angel/Desktop/Mudar/despliegue/mudar-cronometros.timer \
  -t /etc/systemd/system/
sudo systemctl daemon-reload
```
- **`-t`** indica que el último argumento es el **directorio** de destino, no un nombre de archivo. Es lo que permite pasar dos orígenes de una vez.
- **`daemon-reload` no es opcional.** systemd mantiene su catálogo **en memoria**: hasta ese comando, para él las unidades no existen y un `start` respondería que no las encuentra. Es el mismo principio que `EnvironmentFile` —el archivo en disco y el proceso en memoria son cosas distintas— y volverá a aparecer en el 11.4.

**Verificación**
```
systemctl list-unit-files 'mudar-*'
systemd-analyze verify /etc/systemd/system/mudar-cronometros.{service,timer}
systemctl show mudar-cronometros.service -p Type -p User -p WorkingDirectory -p EnvironmentFiles
```
- `mudar-cronometros.service` sale como **`static`**, y **es lo correcto**: no tiene sección `[Install]`, así que no se puede habilitar ni deshabilitar. Quien la activa es el temporizador, que por omisión dispara el servicio de su mismo nombre. Con `[Install]` alguien podría habilitarla suelta y el comando correría sin horario.
- `systemd-analyze verify` es el equivalente de `nginx -t`: **el silencio es el éxito**.
- En lo cargado debe verse `EnvironmentFile=/etc/mudar/env (ignore_errors=no)`. Ese `no` importa: si el archivo faltara, la unidad **falla ruidosamente** en vez de arrancar sin credenciales y morir con un error confuso de Django.

### 11.2 — Lanzar el servicio a mano

```
sudo systemctl start mudar-cronometros.service
journalctl -u mudar-cronometros.service --since today --no-pager
```
Se lanza **antes** de activar el temporizador, para separar «el comando funciona» de «el horario funciona». Con `Type=oneshot`, `start` no devuelve el control hasta que el proceso termina.

**Verificación — la línea que lo prueba todo**
```
python[5612]: 0 cerrados de 0 abiertos
```
Esa la escribe el comando de Python, y demuestra cuatro cosas de golpe: **las credenciales llegaron** (Django importó sin `UndefinedValueError`), **habló con PostgreSQL** (para decir cero tuvo que consultar), **`PYTHONUNBUFFERED` funciona** (la salida aparece en el diario) y corrió como `mudar`.

⚠️ **`○ inactive (dead)` NO es un fallo.** En una unidad `Type=oneshot` es el estado normal tras terminar bien: arrancó, trabajó y salió. Los datos reales son `Result=success` y `ExecMainStatus=0`.

### 11.3 — Activar el temporizador

```
sudo systemctl enable --now mudar-cronometros.timer
```
Dos acciones en un comando: **`enable`** crea el enlace que lo arranca al encender la máquina —para eso sirve la sección `[Install]` del `.timer`— y **`--now`** lo pone en marcha ya.

**Verificación**
```
date '+%Y-%m-%d %H:%M:%S %Z (%z)'
systemctl list-timers mudar-cronometros --all --no-pager
```
```
NEXT                        LEFT  LAST  UNIT                     ACTIVATES
Wed 2026-09-23 21:00:00 -05   7h     -  mudar-cronometros.timer  mudar-cronometros.service
```
🔑 **El `-05` es la comprobación que importa.** Con el sistema en `Europe/Madrid` ese «21:00» habrían sido las 14:00 en la planta. Mirar el desplazamiento, no solo la hora.

También debe verse `active`, `enabled` y `Persistent=yes`.

### 11.4 — Probar que dispara de verdad

**Estar programado y disparar son cosas distintas, y la primera no demuestra la segunda.** Se adelanta el horario con un ***drop-in***, se observa y se restaura. **La unidad original no se toca**, así que deshacerlo es borrar una carpeta.

```
sudo mkdir -p /etc/systemd/system/mudar-cronometros.timer.d
sudo tee /etc/systemd/system/mudar-cronometros.timer.d/prueba.conf > /dev/null << 'EOF'
[Timer]
OnCalendar=
OnCalendar=*-*-* *:*:30
AccuracySec=1s
EOF
sudo systemctl daemon-reload && systemctl list-timers mudar-cronometros --no-pager
```
- ⚠️ **`OnCalendar=` vacío es imprescindible.** Es una directiva de **lista acumulativa**: sin la línea vacía, el horario nuevo se **sumaría** a los tres originales en vez de sustituirlos. Pasa igual con `ExecStart` y otras directivas de lista.
- ⚠️ **`AccuracySec=1s`.** systemd agrupa los disparos con una holgura de **un minuto** por omisión, para despertar varias tareas a la vez y ahorrar energía. Sin esta línea esperarías sin ver nada y pensarías que falla.

**Verificación**
```
journalctl -u mudar-cronometros.service --since today --no-pager | grep -E 'Starting|cerrados'
systemctl list-timers mudar-cronometros --all --no-pager
```
Debe aparecer `LAST` poblado y ejecuciones nuevas en el diario. **Resultado del ensayo (2026-09-23):** tres ejecuciones —una a mano y dos por el temporizador—, todas con `Result=success`.

> **Un regalo de la prueba:** los dos disparos salieron a **cinco segundos** uno del otro, no a un minuto. El primero no encajaba con «segundo 30». Es **`Persistent=true` actuando**: al recargar con un horario nuevo, systemd calculó un disparo «perdido» y lo lanzó de inmediato. Esa es justo la propiedad que importa en producción — si la máquina estuviera apagada a las 21:00, el barrido correría al arrancar en vez de saltarse el día.

**Restaurar, y no se olvida: mientras el fragmento esté, el servicio corre cada minuto.**
```
sudo rm -rf /etc/systemd/system/mudar-cronometros.timer.d && sudo systemctl daemon-reload
systemctl show mudar-cronometros.timer -p TimersCalendar --value
```
Debe volver a `OnCalendar=*-*-* 00,05,21:00:00` con `next_elapse` a las 21:00. El `LAST` conserva la huella de la prueba, que es lo deseable.

### 11.5 — Blindaje *(PENDIENTE, no urgente)*

Trasplantar a esta unidad las **20 directivas** de endurecimiento de `mudar-web.service` (líneas 114-174). **Todas aplican sin modificar:** el perfil del cronómetro es estrictamente más pequeño —no escucha en ningún puerto, no recibe entrada de nadie—, así que un conjunto probado sobre el que hace más vale para el que hace menos.

Método, el mismo del 8.5: **medir antes** con `systemd-analyze security`, trasplantar, instalar, **lanzar a mano y confirmar que sigue funcionando**, medir después. Ese cuarto paso es el que importa: **el blindaje rompe cosas en silencio**, y una directiva de más mata el comando con un error de permisos que no se parece en nada a su causa. **20-35 minutos**, casi todo verificación.

**Por qué no es urgente:** al cronómetro no lo puede alcanzar nadie. Corre tres veces al día, dos segundos, con un comando fijo y sin entrada. La única vía de compromiso es haber comprometido ya el código de `/opt/mudar`, y en ese escenario `mudar-web` cayó primero. **Lo que se gana es consistencia**, no defensa: dos unidades con el mismo usuario, el mismo código y las mismas credenciales, y solo una blindada, es una asimetría que desconcierta a quien lo audite dentro de un año.

## 12. Correo de avisos técnicos (B6) y endurecimiento de Nginx ✅

**Objetivo:** comprobar que un 500 real, dentro de Gunicorn y bajo systemd, genera un aviso por correo, y que un error del cliente no lo genera. En el ensayo el *backend* es el de consola: el aviso se escribe en la salida de Gunicorn, que va al diario. **El diario hace de buzón.** El envío real por Microsoft 365 se prueba en D, con credenciales.

**Por qué filtra así, y no lo decidimos nosotros:** HTTP asigna los 4xx al cliente y los 5xx al servidor, y Django registra los primeros como `WARNING` y los segundos como `ERROR`. Lo único nuestro es el umbral: avisar desde `ERROR`. **Excepción que lo complica:** `DisallowedHost` es un 400 que Django registra como `ERROR` y que, por tanto, **avisa**. De ahí sale el 12.7.

### 12.1 — Encender el interruptor

`ADMINS` vacío es un interruptor, no un olvido: sin destinatario, Django descarta el aviso sin error.
```
sudo grep -E '^(CORREO_AVISOS|EMAIL_BACKEND|DEFAULT_FROM_EMAIL)=' /etc/mudar/env   # debe salir vacío
sudo cp -p /etc/mudar/env /etc/mudar/env.bak
echo 'CORREO_AVISOS=avisos@mudar.test' | sudo tee -a /etc/mudar/env > /dev/null
sudo systemctl restart mudar-web
systemctl is-active mudar-web
```
- **`sudo tee -a` y no `sudo echo … >>`:** la redirección la hace la shell del usuario, sin permisos de root, y fallaría con `Permission denied`.
- **`restart` y no `reload`:** systemd lee `EnvironmentFile` solo al nacer el proceso.
- `EMAIL_BACKEND` **no se declara** en el ensayo: por omisión es el de consola.

**Verificación:** la variable está en el entorno **del proceso vivo**, no solo en el archivo: `sudo cat /proc/<MainPID>/environ | tr '\0' '\n' | grep CORREO`.

### 12.2 — Abrir el buzón

En una **segunda terminal**: `sudo journalctl -u mudar-web -n 0 -f`. El `-n 0` la deja en blanco, así que todo lo que aparezca es consecuencia de lo que se haga después.

### 12.3 — Control negativo: un error que no avisa

```
curl -sk -o /dev/null -w '%{http_code}\n' --resolve app.mudar.test:443:127.0.0.1 \
  https://app.mudar.test/api/ruta-que-no-existe/
```
**404**, `WARNING` en `mudar.log` y **ningún correo**. En el buzón aparece **una línea**, la de acceso de Gunicorn (`--access-logfile -`): es registro, no aviso.

La ruta tiene que empezar por `/api/`: cualquier otra la responde Nginx con `index.html` y Django no se entera.

### 12.4 — Provocar el 500

```
sudo systemctl stop postgresql
systemctl is-active postgresql@16-main              # inactive
curl -sk -o /dev/null -w '%{http_code}\n' --resolve app.mudar.test:443:127.0.0.1 \
  -X POST -H 'Content-Type: application/json' \
  -d '{"username":"prueba","password":"prueba"}' https://app.mudar.test/api/auth/login/
```
- Se comprueba **`postgresql@16-main`**, no `postgresql`: la segunda es una unidad envoltorio que da `active` aunque el clúster esté parado.
- **El usuario y la contraseña tienen que ir rellenos**, aunque sean falsos: con un cuerpo vacío `LoginView` responde 400 en la validación (`views.py:355`) sin llegar a la base. Con los dos campos llega a `authenticate()` (`:368`) y ahí falla.

**Resultado del ensayo (2026-09-24):** **500**, aviso en el buzón y `ERROR django.request` en `mudar.log`. En `seguridad.log`, nada: **un login que termina en 500 no es un intento fallido** y `fail2ban` no lo cuenta.

### 12.5 — Leer el aviso

- 🔴 **`From:` sale vacío.** Es el defecto de B6: `DEFAULT_FROM_EMAIL` cae en `EMAIL_HOST_USER`, vacío. La consola no protesta; **Microsoft 365 rechazaría el correo.** En GTD, `DEFAULT_FROM_EMAIL` es obligatoria.
- **El 500 es genérico, el aviso no:** trae la excepción, la línea (`views.py:368`) y la petición.
- **Los secretos salen tapados** con `********************`: `SafeExceptionReporterFilter` oculta todo nombre con `KEY`, `PASS`, `TOKEN` o `AUTH`, incluida la cabecera `Authorization`. La contraseña del login tampoco sale (`POST: No POST data`), porque DRF lee el JSON por otra vía.
- **Lo que sí sale es un mapa del sistema:** `ALLOWED_HOSTS`, nombre y usuario de la base, rutas y versión de Django. **El destinatario tiene que ser un buzón interno del equipo.**
- El `=3D` y las líneas cortadas con `=` son la codificación *quoted-printable*; un cliente de correo lo decodifica.

**Cambio de código que salió de aquí:** `EMAIL_SUBJECT_PREFIX = '[MUDAR] '` en `settings.py`, para reconocer y filtrar los avisos. 🔴 **Tiene que estar commiteado y subido antes del paso 15**, que clona desde GitHub.

### 12.6 — Restaurar

```
sudo systemctl start postgresql
systemctl is-active postgresql@16-main              # active
```
El login vuelve a responder **401 sin reiniciar Gunicorn**: con `CONN_MAX_AGE = 0` Django abre conexión nueva en cada petición y no guarda ninguna rota. Y ahora sí escribe `Login fallido` en `seguridad.log`.

### 12.7 — Endurecimiento de Nginx

**Objetivo:** que Nginx deje de reenviarlo todo y filtre lo que no es nuestro. Tres cambios, cada uno medido antes y después.

**Por qué, medido en el 12.7.1.** Una petición que pregunta por la IP en vez del dominio —lo que hacen los barridos automáticos, que recorren todo internet y llegan a una IP nueva en horas— caía en el **primer bloque del archivo**, el de MUDAR, a falta de un `default_server`. Consecuencias:
- Por la IP pelada se veía la pantalla de acceso de la aplicación.
- Bajo `/api/`, Django respondía 400 `DisallowedHost`, lo registraba como `ERROR` y **mandaba un aviso por cada petición**.
- 🔴 **El aviso se envía de forma síncrona, dentro del *worker*.** Con SMTP real cuesta del orden de un segundo (sin medir) y hay tres *workers*: un robot insistente los tendría ocupados mandando correos mientras los usuarios esperan. **Deja de ser ruido y pasa a ser una forma barata de frenar la aplicación.**
- `DisallowedHost` va a `mudar.log`, no a `seguridad.log`, así que `fail2ban` tampoco lo vería.

**12.7.1 — Medir el antes**
```
curl -sk -o /dev/null -w '%{http_code}\n' --resolve app.mudar.test:443:127.0.0.1 \
  -H 'Host: 179.50.108.153' https://app.mudar.test/api/                  # 400 + aviso
curl -sk -o /dev/null -w '%{http_code}\n' https://127.0.0.1/            # 200: la aplicación
curl -skI --resolve app.mudar.test:443:127.0.0.1 https://app.mudar.test/ # Server: nginx/1.24.0 (Ubuntu)
```
Se usa la IP de GTD en el `Host` y no `127.0.0.1` porque en el ensayo `ALLOWED_HOSTS` incluye `localhost` y `127.0.0.1`. ⚠️ **En GTD, `ALLOWED_HOSTS` lleva solo `app.mudarcolombia.com`.**

**12.7.2 — Bloque por omisión.** En `nginx-mudar.conf`, antes del bloque del puerto 80:
```nginx
server {
    listen 80 default_server;
    listen 443 ssl http2 default_server;
    server_name _;
    ssl_reject_handshake on;
    return 444;
}
```
- **`ssl_reject_handshake`** rechaza el saludo TLS sin presentar certificado, así que el bloque no necesita uno **y no enseña el nuestro**, que lleva el dominio escrito. Existe desde Nginx 1.19.4.
- **`return 444`** cierra la conexión sin enviar ni una cabecera.
- El nombre se decide **dos veces**: en el saludo TLS (SNI) y en la cabecera `Host`. Quien llega sin SNI lo corta `ssl_reject_handshake`; quien finge el SNI y manda otro `Host` lo corta el `444`.
- Los parámetros del `listen 443` (`ssl http2`) deben coincidir con los del bloque de MUDAR: son del puerto, no del `server`.
- El sitio `default` de Ubuntu **no debe estar activo**, o habría dos `default_server` en el 80 y `nginx -t` fallaría. Comprobado: solo está `mudar` en `sites-enabled`.

**12.7.3 — `server_tokens off;`**, en contexto `http`, arriba del archivo. Va en nuestro archivo y no en `/etc/nginx/nginx.conf` para que viaje con él; allí está comentado, así que no hay duplicado.

**12.7.4 — Cabeceras de seguridad en lo que sirve Nginx.** Archivo nuevo **`despliegue/nginx-cabeceras.conf`** con `Strict-Transport-Security`, `X-Frame-Options DENY` y `X-Content-Type-Options nosniff`, todas con `always`. Se incluye con `include snippets/mudar-cabeceras.conf;` **en cada uno de los tres `location` que sirven del disco**: `/assets/`, `= /index.html` y `/`.
- ⚠️ **No a nivel de `server`:** `add_header` sigue la misma regla de herencia que `proxy_set_header`. `/assets/` e `/index.html` declaran su `Cache-Control` y perderían las heredadas: justo la página de acceso saldría sin protección.
- **No en `/api/`, `/static/` ni `/gestion/`:** Django ya las pone, y saldrían duplicadas.
- 🔴 **HSTS queda declarado en dos sitios**, `settings.py` y `nginx-cabeceras.conf`. Se suben **juntos** a un año (T15).

**Instalación, en este orden.** El archivo de cabeceras va **primero**: si el sitio llega antes, su `include` apunta a un archivo que no existe y `nginx -t` falla.
```
sudo install -o root -g root -m 644 /mnt/c/Users/angel/Desktop/Mudar/despliegue/nginx-cabeceras.conf /etc/nginx/snippets/mudar-cabeceras.conf
sudo install -o root -g root -m 644 /mnt/c/Users/angel/Desktop/Mudar/despliegue/nginx-mudar.conf /etc/nginx/sites-available/mudar
md5sum <los dos orígenes> <los dos destinos>        # iguales de dos en dos
sudo nginx -t && sudo systemctl reload nginx
```

**12.7.5 — Medir el después.** Resultado del ensayo (2026-09-24):
- **Host falso con SNI legítimo:** conexión cortada, `curl` sale con **92** (flujo HTTP/2 cerrado). Ningún aviso y ninguna línea en `mudar.log`.
- **IP pelada por 443:** `curl` **35**, `tlsv1 unrecognized name`.
- **IP pelada por 80:** `curl` **52**, `Empty reply from server`.
- **Dominio legítimo:** `/` 200, `/api/` inexistente 404 y puerto 80 con 301. Igual que antes.
- **Cabecera `Server: nginx`**, sin versión, también en el pie de las páginas de error.
- **Las tres cabeceras** en `/`, `/index.html`, `/assets/…` y `/doms/57`, cada una con su `Cache-Control` intacto. El 404 de `/api/` las trae **una sola vez**: son las de Django.
- **Navegador:** la aplicación funciona entera, `F5` en una ruta interna funciona y la consola no muestra ningún error.

### 12.8 — Limpieza

`sudo rm /etc/mudar/env.bak`. Era una segunda copia de la `SECRET_KEY` y de la contraseña de la base. `/etc/mudar/` queda con un solo archivo, `env`, `root:root 600`.

**Lo que este paso NO cubre:** que la aplicación esté **caída**. Si Gunicorn muere, no queda nadie que envíe el aviso, y el silencio es idéntico al de un día sin incidencias. Hace falta un monitor externo; decisión post-V1.0.

## 13. `ufw` y `fail2ban`

> 🪤 **DOS TRAMPAS DE FECHA, las dos silenciosas. Vienen del 10.8.**
> 1. **Las zonas horarias tienen que coincidir.** `fail2ban` compara la fecha de cada línea de
>    `seguridad.log` **con el reloj del sistema**. Django escribe en `America/Bogota`; si el sistema
>    está en otra zona, todas las líneas caen fuera de la ventana de vigilancia y **no se banea a
>    nadie jamás**, sin error ni aviso.
> 2. **El `datepattern` debe reconocer la coma** de `2026-09-22 12:03:15,883`, antes de los
>    milisegundos. Si no la reconoce, descarta las líneas en silencio.
>
> 🔎 **Y el límite de Nginx condiciona lo que esta jaula puede ver.** Lo que `limit_req` rechaza con
> 429 **no llega a Django** y por tanto **no deja línea**. Medido en el 10.8: de 16 peticiones, 13
> quedaron registradas y 5 no. Por eso el límite se dejó generoso.

**Comandos:** _pendiente_. En WSL solo se puede probar parcialmente.

**Verificación**
- Un login fallido escribe en `seguridad.log` la línea `Login fallido usuario=… ip=…`.
- `fail2ban-regex` sobre `seguridad.log` con el filtro da `Lines matched` mayor que 0. **(T11)**
- `fail2ban-client status <jail>` muestra la jaula activa.
- `ufw status verbose` muestra abiertos solo los puertos previstos.

## 14. Respaldo y restauración

**Comandos:** _pendiente_

**Verificación**
- `pg_restore --list` lee el volcado sin error.
- La restauración en una base **nueva** termina, la aplicación arranca contra ella y los conteos coinciden. **(T7)**
- Junto al volcado queda guardado el `git rev-parse HEAD` del código que lo generó.
- Se anota cuánto tardó la restauración.

## 15. Repetición desde cero

- `wsl --unregister Ubuntu-24.04`, reinstalar y ejecutar los pasos 2 a 14 **solo** con este archivo.
- Todo lo que haya que consultar fuera de este archivo se anota aquí antes de seguir.

## 16. Commit

- Commit de `despliegue/` y de este runbook, después de revisar que no contiene secretos.

---

## Trampas previsibles (T1-T15)

1. **`Host`:** sin `proxy_set_header Host $host`, Django responde 400 DisallowedHost. → Paso 10
2. **`/static/` del panel:** lo sirve WhiteNoise dentro de Gunicorn y Nginx debe reenviarlo. → Paso 10
3. **ACME:** se atiende antes del `try_files` de la SPA y sin redirigir a HTTPS. → Paso 10 (parcial) y D
4. **Tiempos de espera:** Gunicorn corta a los 30 s por omisión, y el resultado es un 502. → Pasos 8 y 10 (configuración) y D (carga real)
5. **Locale `es_CO.UTF-8`:** se genera antes de crear la base. → Pasos 3 y 5
6. **`peer` frente a `scram-sha-256`:** `peer` solo funciona por el socket local. → Paso 5
7. **Versión de PostgreSQL:** 16.9 o posterior. → Pasos 5 y 14
8. **Diario volátil:** se pierde al reiniciar. → Pasos 3 y 8
9. **`PYTHONUNBUFFERED=1`:** sin él, el diario parece vacío. → Paso 8
10. **Formato de `EnvironmentFile`:** systemd no es una shell. → Pasos 4, 7 y 8
11. **fail2ban y la fecha:** si no reconoce la fecha, descarta las líneas en silencio. → Paso 13
12. **Permisos de `/mnt/c`:** WSL los simula y no son reales. → Pasos 6 y 9
13. **Reloj de WSL:** se desfasa al suspender Windows. → Pasos 3 y 11
14. **URL incrustada en el `dist/`:** si está mal, se recompila, no se edita. Desde el 10.7.2 el paquete
    **no lleva dominio**: se comprueba `baseURL:""`, no `localhost`, que da falsos positivos de las
    librerías. → Pasos 9.4 y 10.7
15. **HSTS:** sube de 1 hora a 1 año solo con el certificado estable, y **en dos sitios a la vez**: `SECURE_HSTS_SECONDS` en `settings.py` y `max-age` en `nginx-cabeceras.conf` (desde el 12.7.4). → Bloque D

**Pendientes para el bloque D:** T3 con el dominio y la IP reales, T4 bajo carga real y T15.
