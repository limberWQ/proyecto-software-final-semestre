-- ============================================================
--  init_final.sql — VERSIÓN CORREGIDA v2
--  Sistema de Votación Electrónica — Bolivia
--  Acorde al código real desarrollado (models, services)
--
--  segip_db y tse_db son bases de datos independientes.
--  NO tienen Foreign Keys entre sí.
--
--  CAMBIOS v2:
--   - elecciones: se agregó departamento_id (cada departamento
--     maneja su propia elección presidencial, control independiente)
--   - kioscos: se agregó codigo_vinculacion (código fijo que el
--     operador entrega al celular para vincularlo como kiosco)
-- ============================================================

CREATE DATABASE IF NOT EXISTS segip_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS tse_db
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'segip_user'@'%' IDENTIFIED BY 'segip_pass';
GRANT ALL PRIVILEGES ON segip_db.* TO 'segip_user'@'%';

CREATE USER IF NOT EXISTS 'tse_user'@'%' IDENTIFIED BY 'tse_pass';
GRANT ALL PRIVILEGES ON tse_db.* TO 'tse_user'@'%';

FLUSH PRIVILEGES;


-- ============================================================
--  SEGIP_DB
-- ============================================================
USE segip_db;

CREATE TABLE IF NOT EXISTS departamentos (
    id     TINYINT     NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_departamento (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO departamentos (nombre) VALUES
('LA PAZ'),('COCHABAMBA'),('SANTA CRUZ'),('ORURO'),
('POTOSI'),('TARIJA'),('CHUQUISACA'),('BENI'),('PANDO');

CREATE TABLE IF NOT EXISTS ciudadanos (
    id                INT          NOT NULL AUTO_INCREMENT,
    ci                VARCHAR(12)  NOT NULL,
    complemento       VARCHAR(4)   NULL,
    nombres           VARCHAR(100) NOT NULL,
    apellido_paterno  VARCHAR(80)  NOT NULL,
    apellido_materno  VARCHAR(80)  NULL,
    fecha_nacimiento  DATE         NOT NULL,
    lugar_nacimiento  VARCHAR(120) NULL,
    sexo              ENUM('M','F') NOT NULL,
    estado_civil      ENUM('SOLTERO','CASADO','DIVORCIADO',
                           'VIUDO','UNION_LIBRE') NULL,
    departamento_id   TINYINT      NOT NULL,
    municipio         VARCHAR(80)  NULL,
    domicilio         VARCHAR(200) NULL,
    vivo              TINYINT(1)   NOT NULL DEFAULT 1,
    activo            TINYINT(1)   NOT NULL DEFAULT 1,
    observaciones     TEXT         NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ci (ci),
    INDEX idx_ci (ci),
    CONSTRAINT fk_ciudadano_depto FOREIGN KEY (departamento_id)
        REFERENCES departamentos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS biometria (
    ciudadano_id  INT         NOT NULL,
    foto_hash     VARCHAR(64) NULL,
    huella_hash   VARCHAR(64) NULL,
    updated_at    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (ciudadano_id),
    CONSTRAINT fk_bio_ciudadano FOREIGN KEY (ciudadano_id)
        REFERENCES ciudadanos (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS api_keys (
    id            INT          NOT NULL AUTO_INCREMENT,
    sistema       VARCHAR(50)  NOT NULL,
    api_key_hash  VARCHAR(64)  NOT NULL,
    activo        TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_api_key (api_key_hash)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- API key del TSE: 'TSE-SECRET-KEY-2025'
INSERT IGNORE INTO api_keys (sistema, api_key_hash, activo) VALUES
('TSE', SHA2('TSE-SECRET-KEY-2025', 256), 1);


-- ============================================================
--  TSE_DB
-- ============================================================
USE tse_db;

CREATE TABLE IF NOT EXISTS departamentos (
    id     TINYINT     NOT NULL AUTO_INCREMENT,
    nombre VARCHAR(50) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_departamento (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO departamentos (nombre) VALUES
('LA PAZ'),('COCHABAMBA'),('SANTA CRUZ'),('ORURO'),
('POTOSI'),('TARIJA'),('CHUQUISACA'),('BENI'),('PANDO');

CREATE TABLE IF NOT EXISTS roles (
    id          INT         NOT NULL AUTO_INCREMENT,
    nombre      VARCHAR(30) NOT NULL,
    descripcion TEXT        NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_rol (nombre)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT IGNORE INTO roles (id, nombre, descripcion) VALUES
(1, 'ADMIN',    'Administrador TSE. Crea elecciones y candidatos.'),
(2, 'OPERADOR', 'Operador de mesa. Verifica identidad y habilita kioscos.'),
(3, 'AUDITOR',  'Solo lectura. Accede a la cadena pública y resultados.');

-- ── Recintos ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recintos (
    id              INT          NOT NULL AUTO_INCREMENT,
    codigo          VARCHAR(20)  NOT NULL,
    nombre          VARCHAR(150) NOT NULL,
    direccion       VARCHAR(200) NULL,
    municipio       VARCHAR(80)  NOT NULL,
    departamento_id TINYINT      NOT NULL,
    total_mesas     INT          NOT NULL DEFAULT 1,
    activo          TINYINT(1)   NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_codigo_recinto (codigo),
    CONSTRAINT fk_recinto_depto FOREIGN KEY (departamento_id)
        REFERENCES departamentos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Kioscos ──────────────────────────────────────────────────
-- CORRECCIÓN v2: se agregó codigo_vinculacion (código fijo único
-- que el operador entrega al votante para vincular su celular
-- como kiosco; usado por POST /api/kioscos/vincular)
CREATE TABLE IF NOT EXISTS kioscos (
    id                  INT         NOT NULL AUTO_INCREMENT,
    recinto_id          INT         NOT NULL,
    nombre              VARCHAR(50) NOT NULL,
    codigo_vinculacion  VARCHAR(20) NOT NULL,
    ip_local            VARCHAR(15) NULL,
    activo              TINYINT(1)  NOT NULL DEFAULT 1,
    ultimo_uso          DATETIME    NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_kiosco_recinto (recinto_id, nombre),
    UNIQUE KEY uq_codigo_vinculacion (codigo_vinculacion),
    CONSTRAINT fk_kiosco_recinto FOREIGN KEY (recinto_id)
        REFERENCES recintos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Usuarios TSE ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
    id             INT          NOT NULL AUTO_INCREMENT,
    ci             VARCHAR(12)  NOT NULL,
    nombres        VARCHAR(100) NOT NULL,
    apellidos      VARCHAR(160) NOT NULL,
    email          VARCHAR(120) NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    rol_id         INT          NOT NULL,
    recinto_id     INT          NULL,
    activo         TINYINT(1)   NOT NULL DEFAULT 1,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ci_usuario (ci),
    UNIQUE KEY uq_email (email),
    INDEX idx_rol (rol_id),
    CONSTRAINT fk_usuario_rol     FOREIGN KEY (rol_id)
        REFERENCES roles (id),
    CONSTRAINT fk_usuario_recinto FOREIGN KEY (recinto_id)
        REFERENCES recintos (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Elecciones ───────────────────────────────────────────────
-- CORRECCIÓN v2: se agregó departamento_id. Cada elección
-- presidencial se crea POR DEPARTAMENTO (control independiente);
-- usa recintos y candidatos propios de ese departamento.
CREATE TABLE IF NOT EXISTS elecciones (
    id                INT          NOT NULL AUTO_INCREMENT,
    codigo            VARCHAR(30)  NOT NULL,
    titulo            VARCHAR(200) NOT NULL,
    descripcion       TEXT         NULL,
    tipo              ENUM('PRESIDENCIAL','MUNICIPAL','DEPARTAMENTAL',
                           'REFERENDUM','ASAMBLEA') NOT NULL,
    estado            ENUM('CONFIGURACION','ACTIVA',
                           'SUSPENDIDA','CERRADA')
                                   NOT NULL DEFAULT 'CONFIGURACION',
    departamento_id   TINYINT      NOT NULL,
    fecha_inicio      DATETIME     NOT NULL,
    fecha_fin         DATETIME     NULL,
    clave_publica_pem TEXT         NULL,
    clave_privada_pem TEXT         NULL,
    created_by        INT          NULL,
    created_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_codigo_eleccion (codigo),
    CONSTRAINT fk_eleccion_depto FOREIGN KEY (departamento_id)
        REFERENCES departamentos (id),
    CONSTRAINT fk_eleccion_creador FOREIGN KEY (created_by)
        REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Recintos x Elecciones (N:M) ───────────────────────────────
CREATE TABLE IF NOT EXISTS recintos_elecciones (
    recinto_id  INT NOT NULL,
    eleccion_id INT NOT NULL,
    PRIMARY KEY (recinto_id, eleccion_id),
    CONSTRAINT fk_re_recinto  FOREIGN KEY (recinto_id)
        REFERENCES recintos (id) ON DELETE CASCADE,
    CONSTRAINT fk_re_eleccion FOREIGN KEY (eleccion_id)
        REFERENCES elecciones (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Candidatos ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS candidatos (
    id                       INT          NOT NULL AUTO_INCREMENT,
    eleccion_id              INT          NOT NULL,
    numero_lista             INT          NOT NULL,
    sigla_partido            VARCHAR(20)  NOT NULL,
    nombre_partido           VARCHAR(150) NULL,
    nombres                  VARCHAR(100) NOT NULL,
    apellido_paterno         VARCHAR(80)  NOT NULL,
    apellido_materno         VARCHAR(80)  NULL,
    formula_nombres          VARCHAR(100) NULL,
    formula_apellido_paterno VARCHAR(80)  NULL,
    logo_partido             VARCHAR(200) NULL,
    foto_candidato           VARCHAR(200) NULL,
    color_partido            VARCHAR(7)   NULL,
    propuesta_breve          TEXT         NULL,
    activo                   TINYINT(1)   NOT NULL DEFAULT 1,
    created_at               DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_candidato_lista (eleccion_id, numero_lista),
    CONSTRAINT fk_candidato_eleccion FOREIGN KEY (eleccion_id)
        REFERENCES elecciones (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Padrón Electoral ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS padron_electoral (
    id                    INT          NOT NULL AUTO_INCREMENT,
    eleccion_id           INT          NOT NULL,
    ci                    VARCHAR(12)  NOT NULL,
    complemento           VARCHAR(4)   NULL,
    nombres               VARCHAR(100) NOT NULL,
    apellido_paterno      VARCHAR(80)  NOT NULL,
    apellido_materno      VARCHAR(80)  NULL,
    fecha_nacimiento      DATE         NOT NULL,
    sexo                  ENUM('M','F') NOT NULL,
    departamento_id       TINYINT          NOT NULL,
    recinto_id            INT          NULL,
    mesa_numero           INT          NULL,
    habilitado            TINYINT(1)   NOT NULL DEFAULT 1,
    motivo_inhabilitacion VARCHAR(200) NULL,
    ya_voto               TINYINT(1)   NOT NULL DEFAULT 0,
    hora_voto             DATETIME     NULL,
    habilitado_por        INT          NULL,
    created_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_ci_eleccion (ci, eleccion_id),
    INDEX idx_ci_padron (ci),
    INDEX idx_recinto_mesa (recinto_id, mesa_numero),
    CONSTRAINT fk_padron_eleccion FOREIGN KEY (eleccion_id)
        REFERENCES elecciones (id) ON DELETE CASCADE,
    CONSTRAINT fk_padron_depto    FOREIGN KEY (departamento_id)
        REFERENCES departamentos (id),
    CONSTRAINT fk_padron_recinto  FOREIGN KEY (recinto_id)
        REFERENCES recintos (id),
    CONSTRAINT fk_padron_operador FOREIGN KEY (habilitado_por)
        REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Sesiones de Kiosco ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS sesiones_kiosco (
    id           INT         NOT NULL AUTO_INCREMENT,
    operador_id  INT         NOT NULL,
    padron_id    INT         NOT NULL,
    kiosco_id    INT         NOT NULL,
    token_hash   VARCHAR(64) NOT NULL,
    estado       ENUM('PENDIENTE','ACTIVA','COMPLETADA','EXPIRADA')
                             NOT NULL DEFAULT 'PENDIENTE',
    expira_en    DATETIME    NOT NULL,
    created_at   DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_token (token_hash),
    INDEX idx_estado_sesion (estado),
    CONSTRAINT fk_sesion_operador FOREIGN KEY (operador_id)
        REFERENCES usuarios (id),
    CONSTRAINT fk_sesion_padron   FOREIGN KEY (padron_id)
        REFERENCES padron_electoral (id),
    CONSTRAINT fk_sesion_kiosco   FOREIGN KEY (kiosco_id)
        REFERENCES kioscos (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Índice de Bloques ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS blockchain_bloques (
    id           INT         NOT NULL AUTO_INCREMENT,
    eleccion_id  INT         NOT NULL,
    block_index  INT         NOT NULL,
    prev_hash    VARCHAR(64) NOT NULL,
    block_hash   VARCHAR(64) NOT NULL,
    merkle_root  VARCHAR(64) NOT NULL,
    total_tx     INT         NOT NULL DEFAULT 0,
    nonce        INT         NOT NULL DEFAULT 0,
    timestamp    DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_block_hash (block_hash),
    UNIQUE KEY uq_block_index_eleccion (eleccion_id, block_index),
    INDEX idx_prev_hash (prev_hash),
    CONSTRAINT fk_bloque_eleccion FOREIGN KEY (eleccion_id)
        REFERENCES elecciones (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Recibos ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS recibos (
    id             INT         NOT NULL AUTO_INCREMENT,
    padron_id      INT         NOT NULL,
    eleccion_id    INT         NOT NULL,
    codigo_recibo  VARCHAR(32) NOT NULL,
    block_hash     VARCHAR(64) NOT NULL,
    impreso        TINYINT(1)  NOT NULL DEFAULT 0,
    created_at     DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_codigo_recibo (codigo_recibo),
    UNIQUE KEY uq_padron_eleccion (padron_id, eleccion_id),
    CONSTRAINT fk_recibo_padron   FOREIGN KEY (padron_id)
        REFERENCES padron_electoral (id),
    CONSTRAINT fk_recibo_eleccion FOREIGN KEY (eleccion_id)
        REFERENCES elecciones (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Conteo Rápido ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conteos (
    id           INT      NOT NULL AUTO_INCREMENT,
    eleccion_id  INT      NOT NULL,
    candidato_id INT      NULL,
    tipo         ENUM('VALIDO','BLANCO','NULO') NOT NULL,
    total_votos  INT      NOT NULL DEFAULT 0,
    updated_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_conteo (eleccion_id, candidato_id, tipo),
    CONSTRAINT fk_conteo_eleccion  FOREIGN KEY (eleccion_id)
        REFERENCES elecciones (id) ON DELETE CASCADE,
    CONSTRAINT fk_conteo_candidato FOREIGN KEY (candidato_id)
        REFERENCES candidatos (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ── Audit Log ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id               BIGINT      NOT NULL AUTO_INCREMENT,
    usuario_id       INT         NULL,
    eleccion_id      INT         NULL,
    accion           VARCHAR(50) NOT NULL,
    descripcion      TEXT        NULL,
    ip_hash          VARCHAR(64) NULL,
    hash_integridad  VARCHAR(64) NOT NULL,
    created_at       DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_usuario_audit  (usuario_id),
    INDEX idx_eleccion_audit (eleccion_id),
    INDEX idx_accion_audit   (accion),
    CONSTRAINT fk_audit_usuario  FOREIGN KEY (usuario_id)
        REFERENCES usuarios (id) ON DELETE SET NULL,
    CONSTRAINT fk_audit_eleccion FOREIGN KEY (eleccion_id)
        REFERENCES elecciones (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
--  USUARIO ADMIN INICIAL
--  CI: 0000000  Email: admin@tse.gob.bo  Password: Admin123!
--  Hash generado con werkzeug.security.generate_password_hash
--  (pbkdf2:sha256). Cambiar esta contraseña tras el primer login.
-- ============================================================
INSERT IGNORE INTO usuarios (id, ci, nombres, apellidos, email, password_hash, rol_id, activo)
VALUES (
    1, '0000000', 'Administrador', 'TSE', 'admin@tse.gob.bo',
    'pbkdf2:sha256:1000000$s5skDs5RhfD1lPuH$4ee099dbd48c5af1155dbd4117ae6b2e01b6792b2c1cf34450254c4643bfba39',
    1, 1
);