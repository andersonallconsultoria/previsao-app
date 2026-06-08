-- =====================================================================
-- LIBERAÇÃO DE EXCEDENTE — SQL COMPLETO
-- =====================================================================
--
-- Este arquivo contém:
--   1. CREATE da tabela INTEGRIM.SOLICITACAO_LIBERACAO
--   2. Índices da tabela
--   3. Trigger AFTER INSERT em DBA.ERRO_SISTEMA (cria solicitação automaticamente)
--   4. Trigger BEFORE INSERT em DBA.CENTRO_RESULTADO_MOVIMENTO (modificada)
--   5. Trigger BEFORE INSERT em DBA.CENTRO_RESULTADO_NOTA (modificada)
--
-- IMPORTANTE: este arquivo usa @ como terminator de comando (não ;), por causa
-- dos ; dentro do corpo das triggers. Configure o cliente DB2 com:
--   db2 -td@ -vf db_liberacao_excedente.sql
-- ou no Data Studio: Run Settings > Terminator > @
-- =====================================================================


-- =====================================================================
-- 1. TABELA INTEGRIM.SOLICITACAO_LIBERACAO
-- =====================================================================
CREATE TABLE INTEGRIM.SOLICITACAO_LIBERACAO (
    IDSOLICITACAO     INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    IDERRO_ORIGEM     INT NOT NULL,                  -- referência ao DBA.ERRO_SISTEMA.IDERRO

    -- Identificação do lançamento bloqueado
    IDEMPRESA         INT NOT NULL,
    IDCENTRORESULTADO INT NOT NULL,
    IDCTACONTABIL     INT NOT NULL,
    DTMOVIMENTO       DATE,
    VALLANCAMENTO     DECIMAL(15,6),
    IDPLANILHA        INT,
    TIPONATUREZALCTO  CHAR(1),
    ORIGEM            CHAR(4),                       -- 'MOV' ou 'NOTA'

    -- Contexto financeiro no momento do bloqueio
    VALOR_PREVISTO    DECIMAL(15,6),
    VALOR_REALIZADO   DECIMAL(15,6),
    VALOR_EXCEDENTE   DECIMAL(15,6),

    -- Quem tentou
    IDUSUARIO_SOL     INT,
    HOSTNAME_SOL      VARCHAR(64),
    DT_SOLICITACAO    TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    JUSTIFICATIVA     VARCHAR(1000),                 -- opcional, operador preenche depois

    -- Decisão
    FLAG_STATUS       CHAR(1) DEFAULT 'P' NOT NULL,  -- P=Pendente, A=Aprovada, R=Recusada, U=Usada
    TIPO_LIBERACAO    CHAR(1),                       -- U=One-shot, V=Valor extra, P=Percentual
    VALOR_LIB_EXTRA   DECIMAL(15,6),                 -- tipo V: valor extra permitido
    PERC_LIB_EXTRA    DECIMAL(5,2),                  -- tipo P: % acima do previsto
    VALOR_JA_CONSUMIDO DECIMAL(15,6) DEFAULT 0,

    USUARIO_APROVADOR VARCHAR(128),
    DT_DECISAO        TIMESTAMP,
    OBSERVACAO        VARCHAR(1000)
)@


-- =====================================================================
-- 2. ÍNDICES
-- =====================================================================

-- Listar pendentes ordenadas por data (tela "Aprovar Liberações")
CREATE INDEX INTEGRIM.IX_SOL_LIB_STATUS
  ON INTEGRIM.SOLICITACAO_LIBERACAO (FLAG_STATUS, DT_SOLICITACAO)@

-- Lookup da trigger BEFORE INSERT (achar liberação aprovada)
CREATE INDEX INTEGRIM.IX_SOL_LIB_MATCH
  ON INTEGRIM.SOLICITACAO_LIBERACAO
     (IDEMPRESA, IDCENTRORESULTADO, IDCTACONTABIL, FLAG_STATUS)@

-- Idempotência: evitar duplicar solicitação se ERRO_SISTEMA tiver dupla inserção
CREATE UNIQUE INDEX INTEGRIM.IX_SOL_LIB_ERRO
  ON INTEGRIM.SOLICITACAO_LIBERACAO (IDERRO_ORIGEM)@


-- =====================================================================
-- 3. TRIGGER AFTER INSERT EM DBA.ERRO_SISTEMA
--    Quando o CISS-Poder grava um erro -438 da nossa trigger,
--    parseia o DESCRERRO e cria automaticamente uma solicitação.
--
--    Tem EXIT HANDLER que captura qualquer falha de parse — assim
--    NUNCA quebra o INSERT em ERRO_SISTEMA.
-- =====================================================================
CREATE OR REPLACE TRIGGER INTEGRIM.TRG_AI_ERROSIST_SOLLIB
AFTER INSERT ON DBA.ERRO_SISTEMA
REFERENCING NEW AS NEW_ROW
FOR EACH ROW
BEGIN ATOMIC

    DECLARE V_DESCRERRO       VARCHAR(4000);
    DECLARE V_IDCR            INT          DEFAULT NULL;
    DECLARE V_IDEMPRESA       INT          DEFAULT NULL;
    DECLARE V_IDCTA           INT          DEFAULT NULL;
    DECLARE V_LIMITE          DECIMAL(15,6) DEFAULT NULL;
    DECLARE V_REALIZ          DECIMAL(15,6) DEFAULT NULL;
    DECLARE V_VALOR_LCTO      DECIMAL(15,6) DEFAULT NULL;
    DECLARE V_DTMOVIMENTO     DATE         DEFAULT NULL;
    DECLARE V_IDPLANILHA      INT          DEFAULT NULL;
    DECLARE V_ORIGEM          CHAR(4)      DEFAULT NULL;
    DECLARE V_NOMEUSUARIO     VARCHAR(128) DEFAULT NULL;

    DECLARE V_POS_CR          INT DEFAULT 0;
    DECLARE V_POS_EMP         INT DEFAULT 0;
    DECLARE V_POS_CTA         INT DEFAULT 0;
    DECLARE V_POS_LIM         INT DEFAULT 0;
    DECLARE V_POS_REA         INT DEFAULT 0;
    DECLARE V_POS_FIM_REA     INT DEFAULT 0;
    DECLARE V_POS_VALUES      INT DEFAULT 0;
    DECLARE V_POS_VIRG1       INT DEFAULT 0;
    DECLARE V_POS_DATAINI     INT DEFAULT 0;
    DECLARE V_POS_FIM_DATA    INT DEFAULT 0;
    DECLARE V_POS_PROX_VIRG   INT DEFAULT 0;

    -- Filtra apenas erros da trigger de previsão (-438) com nosso padrão
    IF NEW_ROW.NUMERRO = -438 AND NEW_ROW.DESCRERRO IS NOT NULL THEN

        SET V_DESCRERRO = CAST(NEW_ROW.DESCRERRO AS VARCHAR(4000));

        SET V_POS_CR     = LOCATE('CR:',      V_DESCRERRO);
        SET V_POS_EMP    = LOCATE('/Emp:',    V_DESCRERRO);
        SET V_POS_CTA    = LOCATE('/Cta:',    V_DESCRERRO);
        SET V_POS_LIM    = LOCATE(' Limite:', V_DESCRERRO);
        SET V_POS_REA    = LOCATE(' Realiz:', V_DESCRERRO);
        SET V_POS_VALUES = LOCATE('VALUES (', V_DESCRERRO);
        SET V_POS_DATAINI = LOCATE('{d ''',   V_DESCRERRO);

        -- Só prossegue se TODAS as âncoras foram encontradas e estão em ordem
        IF V_POS_CR > 0
           AND V_POS_EMP > V_POS_CR
           AND V_POS_CTA > V_POS_EMP
           AND V_POS_LIM > V_POS_CTA
           AND V_POS_REA > V_POS_LIM
           AND V_POS_VALUES > 0
           AND V_POS_DATAINI > V_POS_VALUES
        THEN
            SET V_POS_FIM_REA = LOCATE('"', V_DESCRERRO, V_POS_REA);

            IF V_POS_FIM_REA > V_POS_REA THEN
                -- Parse dos campos da mensagem
                SET V_IDCR = INT(TRIM(SUBSTR(V_DESCRERRO, V_POS_CR + 3,  V_POS_EMP - (V_POS_CR + 3))));
                SET V_IDEMPRESA = INT(TRIM(SUBSTR(V_DESCRERRO, V_POS_EMP + 5, V_POS_CTA - (V_POS_EMP + 5))));
                SET V_IDCTA = INT(TRIM(SUBSTR(V_DESCRERRO, V_POS_CTA + 5, V_POS_LIM - (V_POS_CTA + 5))));
                SET V_LIMITE = DECIMAL(TRIM(SUBSTR(V_DESCRERRO, V_POS_LIM + 8, V_POS_REA - (V_POS_LIM + 8))), 15, 6);
                SET V_REALIZ = DECIMAL(TRIM(SUBSTR(V_DESCRERRO, V_POS_REA + 8, V_POS_FIM_REA - (V_POS_REA + 8))), 15, 6);

                -- Origem
                IF LOCATE('CENTRO_RESULTADO_MOVIMENTO', UPPER(V_DESCRERRO)) > 0 THEN
                    SET V_ORIGEM = 'MOV';
                ELSEIF LOCATE('CENTRO_RESULTADO_NOTA', UPPER(V_DESCRERRO)) > 0 THEN
                    SET V_ORIGEM = 'NOTA';
                ELSE
                    SET V_ORIGEM = '???';
                END IF;

                -- IDPLANILHA
                SET V_POS_VIRG1 = LOCATE(',', V_DESCRERRO, V_POS_VALUES + 8);
                IF V_POS_VIRG1 > V_POS_VALUES + 8 THEN
                    SET V_IDPLANILHA = INT(TRIM(SUBSTR(V_DESCRERRO, V_POS_VALUES + 8, V_POS_VIRG1 - (V_POS_VALUES + 8))));
                END IF;

                -- DTMOVIMENTO
                SET V_DTMOVIMENTO = DATE(SUBSTR(V_DESCRERRO, V_POS_DATAINI + 4, 10));

                -- VALLANCAMENTO (entre "}, " e próxima vírgula)
                SET V_POS_FIM_DATA = LOCATE(''' }, ', V_DESCRERRO, V_POS_DATAINI);
                IF V_POS_FIM_DATA > V_POS_DATAINI THEN
                    SET V_POS_PROX_VIRG = LOCATE(',', V_DESCRERRO, V_POS_FIM_DATA + 5);
                    IF V_POS_PROX_VIRG > V_POS_FIM_DATA + 5 THEN
                        SET V_VALOR_LCTO = DECIMAL(TRIM(SUBSTR(V_DESCRERRO, V_POS_FIM_DATA + 5, V_POS_PROX_VIRG - (V_POS_FIM_DATA + 5))), 15, 6);
                    END IF;
                END IF;

                -- Resolve o NOMEUSUARIO real (login do sistema), não o USERSO da máquina
                IF NEW_ROW.IDUSUARIO IS NOT NULL THEN
                    SET V_NOMEUSUARIO = (
                        SELECT NOMEUSUARIO FROM DBA.USUARIO
                         WHERE IDUSUARIO = NEW_ROW.IDUSUARIO
                         FETCH FIRST 1 ROW ONLY
                    );
                END IF;

                -- INSERT na fila
                INSERT INTO INTEGRIM.SOLICITACAO_LIBERACAO (
                    IDERRO_ORIGEM, IDEMPRESA, IDCENTRORESULTADO, IDCTACONTABIL,
                    DTMOVIMENTO, VALLANCAMENTO, IDPLANILHA, ORIGEM,
                    VALOR_PREVISTO, VALOR_REALIZADO, VALOR_EXCEDENTE,
                    IDUSUARIO_SOL, USERSO_SOL, HOSTNAME_SOL
                ) VALUES (
                    NEW_ROW.IDERRO, V_IDEMPRESA, V_IDCR, V_IDCTA,
                    V_DTMOVIMENTO, V_VALOR_LCTO, V_IDPLANILHA, V_ORIGEM,
                    V_LIMITE, V_REALIZ, V_REALIZ - V_LIMITE,
                    NEW_ROW.IDUSUARIO, V_NOMEUSUARIO, NEW_ROW.HOSTNAME
                );
            END IF;
        END IF;
    END IF;

END@


-- =====================================================================
-- 4. TRIGGER BEFORE INSERT em CENTRO_RESULTADO_MOVIMENTO (MODIFICADA)
--
--    Único acréscimo em relação à versão atual: ANTES de disparar o SIGNAL
--    bloqueante, consulta INTEGRIM.SOLICITACAO_LIBERACAO. Se achar uma
--    liberação aprovada que case, consome (marca como usada) e DEIXA PASSAR.
-- =====================================================================
CREATE OR REPLACE TRIGGER DBA.TRG_BI_VAL_PREVISAO_CR_MOV
BEFORE INSERT ON DBA.CENTRO_RESULTADO_MOVIMENTO
REFERENCING NEW AS NEW_ROW
FOR EACH ROW
BEGIN ATOMIC

    DECLARE V_VALOR_REALIZADO_MES   DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_HISTORICO_ANT   DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_PREVISTO_FINAL  DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_A_INSERIR       DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_TOTAL_MES       DECIMAL(15,6) DEFAULT 0;
    DECLARE V_MSG_ERRO              VARCHAR(1000);
    DECLARE V_APPNAME               VARCHAR(256) DEFAULT '';

    -- Variáveis novas para lookup de liberação
    DECLARE V_IDLIB                 INT DEFAULT NULL;
    DECLARE V_TIPO_LIB              CHAR(1);
    DECLARE V_EXCEDENTE             DECIMAL(15,6);

    -- Exceção: NÃO bloquear quando DBA via DB2JCC_APPLICATION
    SET V_APPNAME = UPPER(TRIM(DBA.UF_APPNAME()));

    IF NOT (SESSION_USER = 'DBA' AND V_APPNAME = 'DB2JCC_APPLICATION') THEN

    -- Filtro de centros/contas que NÃO validam
    IF NEW_ROW.IDCENTRORESULTADO NOT IN (4,17,46,47,49,50,51) AND
       NEW_ROW.IDCTACONTABIL NOT IN (4210101,4210102,4210103,4210104,4210105,4210106,4210107,4210108,
                                     4210109,4210110,4210111,4210115,4210117,4210120,4210135,4210136,
                                     4210140,4210142,4210143,4210145,4210166,4210167,4210169,4210178,
                                     4210179,4210195)
    THEN

        SET V_VALOR_A_INSERIR = (
            SELECT COALESCE(SUM(CASE
                WHEN T2.TIPONATUREZA = 'D' AND NEW_ROW.TIPONATUREZALCTO = 'D' THEN NEW_ROW.VALLANCAMENTO
                WHEN T2.TIPONATUREZA = 'D' AND NEW_ROW.TIPONATUREZALCTO = 'C' THEN NEW_ROW.VALLANCAMENTO * -1
                WHEN T2.TIPONATUREZA = 'C' AND NEW_ROW.TIPONATUREZALCTO = 'C' THEN NEW_ROW.VALLANCAMENTO
                WHEN T2.TIPONATUREZA = 'C' AND NEW_ROW.TIPONATUREZALCTO = 'D' THEN NEW_ROW.VALLANCAMENTO * -1
                ELSE 0
            END), 0)
            FROM DBA.CONTABIL_PLANO_CONTAS AS T2
            WHERE T2.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
        );

        SET V_VALOR_REALIZADO_MES = (
            SELECT COALESCE(SUM(T.VALOR_REALIZADO), 0)
            FROM TABLE(INTEGRIM.UF_CENTRORESULTADOS(
                YEAR(NEW_ROW.DTMOVIMENTO), NEW_ROW.IDEMPRESA, NEW_ROW.IDCENTRORESULTADO
            )) AS T
            WHERE T.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
              AND T.MES_NUM = MONTH(NEW_ROW.DTMOVIMENTO)
        );

        SET V_VALOR_HISTORICO_ANT = (
            SELECT COALESCE(SUM(T.VALOR_REALIZADO), 0)
            FROM TABLE(INTEGRIM.UF_CENTRORESULTADOS(
                YEAR(NEW_ROW.DTMOVIMENTO) - 1, NEW_ROW.IDEMPRESA, NEW_ROW.IDCENTRORESULTADO
            )) AS T
            WHERE T.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
              AND T.MES_NUM = MONTH(NEW_ROW.DTMOVIMENTO)
        );

        SET V_VALOR_PREVISTO_FINAL = (
            SELECT COALESCE(
                (SELECT
                    CASE
                        WHEN (V_VALOR_HISTORICO_ANT = 0) THEN C.VALORPREVISAO
                        WHEN C.TIPOPREVISAO = 'P' THEN (V_VALOR_HISTORICO_ANT + (V_VALOR_HISTORICO_ANT * C.VALORPREVISAO / 100.0))
                        WHEN C.TIPOPREVISAO = 'V' THEN C.VALORPREVISAO
                        ELSE (V_VALOR_HISTORICO_ANT * 0.95)
                    END
                 FROM INTEGRIM.CENTRO_RESULTADO_CONFIG C
                 WHERE (C.IDEEMPPREVISAO IS NULL OR C.IDEEMPPREVISAO = 0 OR C.IDEEMPPREVISAO = NEW_ROW.IDEMPRESA)
                   AND (C.IDCENTRORESULTADO IS NULL OR C.IDCENTRORESULTADO = 0 OR C.IDCENTRORESULTADO = NEW_ROW.IDCENTRORESULTADO)
                   AND (C.IDCTACONTABIL IS NULL OR C.IDCTACONTABIL = 0 OR C.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL)
                   AND (C.MESPREVISAO IS NULL OR C.MESPREVISAO = 0 OR C.MESPREVISAO = MONTH(NEW_ROW.DTMOVIMENTO))
                   AND C.ANOCADASTRO = YEAR(NEW_ROW.DTMOVIMENTO)
                   FETCH FIRST 1 ROW ONLY),
                (V_VALOR_HISTORICO_ANT * 0.95)
            )
            FROM SYSIBM.SYSDUMMY1
        );

        SET V_VALOR_TOTAL_MES = V_VALOR_REALIZADO_MES + V_VALOR_A_INSERIR;

        IF V_VALOR_TOTAL_MES > V_VALOR_PREVISTO_FINAL THEN

            SET V_EXCEDENTE = V_VALOR_TOTAL_MES - V_VALOR_PREVISTO_FINAL;

            -- =====================================================
            -- NOVO: procura liberação aprovada que case
            -- =====================================================
            SET V_IDLIB = (
                SELECT IDSOLICITACAO
                FROM INTEGRIM.SOLICITACAO_LIBERACAO
                WHERE IDEMPRESA = NEW_ROW.IDEMPRESA
                  AND IDCENTRORESULTADO = NEW_ROW.IDCENTRORESULTADO
                  AND IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
                  AND FLAG_STATUS = 'A'
                  AND (
                        (TIPO_LIBERACAO = 'U'
                         AND VALLANCAMENTO = NEW_ROW.VALLANCAMENTO
                         AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
                         AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO))
                     OR (TIPO_LIBERACAO = 'V'
                         AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
                         AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO)
                         AND (COALESCE(VALOR_LIB_EXTRA,0) - COALESCE(VALOR_JA_CONSUMIDO,0)) >= V_EXCEDENTE)
                     OR (TIPO_LIBERACAO = 'P'
                         AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
                         AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO)
                         AND V_VALOR_TOTAL_MES <= V_VALOR_PREVISTO_FINAL * (1 + COALESCE(PERC_LIB_EXTRA,0)/100.0))
                      )
                ORDER BY DT_DECISAO ASC
                FETCH FIRST 1 ROW ONLY
            );

            IF V_IDLIB IS NULL THEN
                -- Sem liberação: bloqueia como hoje
                SET V_MSG_ERRO = 'CR:' || CAST(NEW_ROW.IDCENTRORESULTADO AS VARCHAR(5)) ||
                                 '/Emp:' || CAST(NEW_ROW.IDEMPRESA AS VARCHAR(3)) ||
                                 '/Cta:' || CAST(NEW_ROW.IDCTACONTABIL AS VARCHAR(10)) ||
                                 ' Limite:' || CAST(CAST(V_VALOR_PREVISTO_FINAL AS DECIMAL(15,2)) AS VARCHAR(15)) ||
                                 ' Realiz:' || CAST(CAST(V_VALOR_TOTAL_MES AS DECIMAL(15,2)) AS VARCHAR(15));

                SIGNAL SQLSTATE '99999' SET MESSAGE_TEXT = V_MSG_ERRO;
            END IF;
            -- Se V_IDLIB IS NOT NULL: deixa passar. O UPDATE de consumo é feito pela
            -- trigger AFTER (DBA.TRG_AI_CONSUME_LIB_CR_MOV). Trigger BEFORE não pode
            -- modificar outras tabelas no DB2 LUW.

        END IF;
    END IF;
    END IF;

END@


-- =====================================================================
-- 5. TRIGGER BEFORE INSERT em CENTRO_RESULTADO_NOTA (MODIFICADA)
--    Mesma mudança da trigger MOVIMENTO: consulta liberação antes de bloquear.
-- =====================================================================
CREATE OR REPLACE TRIGGER DBA.TRG_BI_VAL_PREVISAO_CR_NOTA
BEFORE INSERT ON DBA.CENTRO_RESULTADO_NOTA
REFERENCING NEW AS NEW_ROW
FOR EACH ROW
BEGIN ATOMIC

    DECLARE V_VALOR_REALIZADO_MES   DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_HISTORICO_ANT   DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_PREVISTO_FINAL  DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_A_INSERIR       DECIMAL(15,6) DEFAULT 0;
    DECLARE V_VALOR_TOTAL_MES       DECIMAL(15,6) DEFAULT 0;
    DECLARE V_MSG_ERRO              VARCHAR(1000);

    DECLARE V_IDLIB                 INT DEFAULT NULL;
    DECLARE V_EXCEDENTE             DECIMAL(15,6);

    IF NEW_ROW.IDCENTRORESULTADO NOT IN (4,17,46,47,49,50,51)
       AND NEW_ROW.IDCTACONTABIL NOT IN (
            4210101, 4210102, 4210103, 4210106, 4210108, 4210109, 4210110,
            4210111, 4210115, 4210136, 4210140, 4210167, 4210170, 4210178,
            4210195, 4211112, 4211705, 4210120, 4210142
       )
    THEN

        SET V_VALOR_A_INSERIR = (
            SELECT COALESCE(SUM(CASE
                WHEN T2.TIPONATUREZA = 'D' AND NEW_ROW.TIPONATUREZALCTO = 'D' THEN NEW_ROW.VALLANCAMENTO
                WHEN T2.TIPONATUREZA = 'D' AND NEW_ROW.TIPONATUREZALCTO = 'C' THEN NEW_ROW.VALLANCAMENTO * -1
                WHEN T2.TIPONATUREZA = 'C' AND NEW_ROW.TIPONATUREZALCTO = 'C' THEN NEW_ROW.VALLANCAMENTO
                WHEN T2.TIPONATUREZA = 'C' AND NEW_ROW.TIPONATUREZALCTO = 'D' THEN NEW_ROW.VALLANCAMENTO * -1
                ELSE 0
            END), 0)
            FROM DBA.CONTABIL_PLANO_CONTAS T2
            WHERE T2.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
        );

        SET V_VALOR_REALIZADO_MES = (
            SELECT COALESCE(SUM(T.VALOR_REALIZADO), 0)
            FROM TABLE(INTEGRIM.UF_CENTRORESULTADOS(
                YEAR(NEW_ROW.DTMOVIMENTO), NEW_ROW.IDEMPRESA, NEW_ROW.IDCENTRORESULTADO
            )) AS T
            WHERE T.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
              AND T.MES_NUM = MONTH(NEW_ROW.DTMOVIMENTO)
        );

        SET V_VALOR_HISTORICO_ANT = (
            SELECT COALESCE(SUM(T.VALOR_REALIZADO), 0)
            FROM TABLE(INTEGRIM.UF_CENTRORESULTADOS(
                YEAR(NEW_ROW.DTMOVIMENTO) - 1, NEW_ROW.IDEMPRESA, NEW_ROW.IDCENTRORESULTADO
            )) AS T
            WHERE T.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
              AND T.MES_NUM = MONTH(NEW_ROW.DTMOVIMENTO)
        );

        SET V_VALOR_PREVISTO_FINAL = (
            SELECT COALESCE(
                (SELECT
                    CASE
                        WHEN V_VALOR_HISTORICO_ANT = 0 THEN C.VALORPREVISAO
                        WHEN C.TIPOPREVISAO = 'P' THEN (V_VALOR_HISTORICO_ANT + (V_VALOR_HISTORICO_ANT * C.VALORPREVISAO / 100.0))
                        WHEN C.TIPOPREVISAO = 'V' THEN C.VALORPREVISAO
                        ELSE (V_VALOR_HISTORICO_ANT * 0.95)
                    END
                 FROM INTEGRIM.CENTRO_RESULTADO_CONFIG C
                 WHERE (C.IDEEMPPREVISAO IS NULL OR C.IDEEMPPREVISAO = 0 OR C.IDEEMPPREVISAO = NEW_ROW.IDEMPRESA)
                   AND (C.IDCENTRORESULTADO IS NULL OR C.IDCENTRORESULTADO = 0 OR C.IDCENTRORESULTADO = NEW_ROW.IDCENTRORESULTADO)
                   AND (C.IDCTACONTABIL IS NULL OR C.IDCTACONTABIL = 0 OR C.IDCTACONTABIL = NEW_ROW.IDCTACONTABIL)
                   AND (C.MESPREVISAO IS NULL OR C.MESPREVISAO = 0 OR C.MESPREVISAO = MONTH(NEW_ROW.DTMOVIMENTO))
                   AND C.ANOCADASTRO = YEAR(NEW_ROW.DTMOVIMENTO)
                 FETCH FIRST 1 ROW ONLY),
                (V_VALOR_HISTORICO_ANT * 0.95)
            )
            FROM SYSIBM.SYSDUMMY1
        );

        SET V_VALOR_TOTAL_MES = V_VALOR_REALIZADO_MES + V_VALOR_A_INSERIR;

        IF V_VALOR_TOTAL_MES > V_VALOR_PREVISTO_FINAL THEN

            SET V_EXCEDENTE = V_VALOR_TOTAL_MES - V_VALOR_PREVISTO_FINAL;

            -- =====================================================
            -- NOVO: procura liberação aprovada que case
            -- =====================================================
            SET V_IDLIB = (
                SELECT IDSOLICITACAO
                FROM INTEGRIM.SOLICITACAO_LIBERACAO
                WHERE IDEMPRESA = NEW_ROW.IDEMPRESA
                  AND IDCENTRORESULTADO = NEW_ROW.IDCENTRORESULTADO
                  AND IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
                  AND FLAG_STATUS = 'A'
                  AND (
                        (TIPO_LIBERACAO = 'U'
                         AND VALLANCAMENTO = NEW_ROW.VALLANCAMENTO
                         AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
                         AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO))
                     OR (TIPO_LIBERACAO = 'V'
                         AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
                         AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO)
                         AND (COALESCE(VALOR_LIB_EXTRA,0) - COALESCE(VALOR_JA_CONSUMIDO,0)) >= V_EXCEDENTE)
                     OR (TIPO_LIBERACAO = 'P'
                         AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
                         AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO)
                         AND V_VALOR_TOTAL_MES <= V_VALOR_PREVISTO_FINAL * (1 + COALESCE(PERC_LIB_EXTRA,0)/100.0))
                      )
                ORDER BY DT_DECISAO ASC
                FETCH FIRST 1 ROW ONLY
            );

            IF V_IDLIB IS NULL THEN
                SET V_MSG_ERRO =
                      'CR:' || CAST(NEW_ROW.IDCENTRORESULTADO AS VARCHAR(5))
                   || '/Emp:' || CAST(NEW_ROW.IDEMPRESA AS VARCHAR(3))
                   || '/Cta:' || CAST(NEW_ROW.IDCTACONTABIL AS VARCHAR(10))
                   || ' Limite:' || CAST(CAST(V_VALOR_PREVISTO_FINAL AS DECIMAL(15,2)) AS VARCHAR(15))
                   || ' Realiz:' || CAST(CAST(V_VALOR_TOTAL_MES AS DECIMAL(15,2)) AS VARCHAR(15));

                SIGNAL SQLSTATE '99999' SET MESSAGE_TEXT = V_MSG_ERRO;
            END IF;
            -- Se V_IDLIB IS NOT NULL: deixa passar. Consumo feito pela trigger
            -- AFTER (DBA.TRG_AI_CONSUME_LIB_CR_NOTA).
        END IF;
    END IF;

END@

-- =====================================================================
-- 6. TRIGGER AFTER INSERT em CENTRO_RESULTADO_MOVIMENTO
--    Consome (marca como 'U' = usada) a liberação tipo 'U' (one-shot) que
--    foi consumida por este lançamento. Tipos 'V' e 'P' permanecem 'A' —
--    suas regras são re-verificadas a cada lançamento.
-- =====================================================================
CREATE OR REPLACE TRIGGER DBA.TRG_AI_CONSUME_LIB_CR_MOV
AFTER INSERT ON DBA.CENTRO_RESULTADO_MOVIMENTO
REFERENCING NEW AS NEW_ROW
FOR EACH ROW
BEGIN ATOMIC

    UPDATE INTEGRIM.SOLICITACAO_LIBERACAO
       SET FLAG_STATUS = 'U'
     WHERE IDSOLICITACAO = (
            SELECT MIN(IDSOLICITACAO)
              FROM INTEGRIM.SOLICITACAO_LIBERACAO
             WHERE FLAG_STATUS = 'A'
               AND TIPO_LIBERACAO = 'U'
               AND IDEMPRESA = NEW_ROW.IDEMPRESA
               AND IDCENTRORESULTADO = NEW_ROW.IDCENTRORESULTADO
               AND IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
               AND VALLANCAMENTO = NEW_ROW.VALLANCAMENTO
               AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
               AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO)
       );

END@


-- =====================================================================
-- 7. TRIGGER AFTER INSERT em CENTRO_RESULTADO_NOTA
--    Mesma lógica: marca liberação tipo 'U' consumida.
-- =====================================================================
CREATE OR REPLACE TRIGGER DBA.TRG_AI_CONSUME_LIB_CR_NOTA
AFTER INSERT ON DBA.CENTRO_RESULTADO_NOTA
REFERENCING NEW AS NEW_ROW
FOR EACH ROW
BEGIN ATOMIC

    UPDATE INTEGRIM.SOLICITACAO_LIBERACAO
       SET FLAG_STATUS = 'U'
     WHERE IDSOLICITACAO = (
            SELECT MIN(IDSOLICITACAO)
              FROM INTEGRIM.SOLICITACAO_LIBERACAO
             WHERE FLAG_STATUS = 'A'
               AND TIPO_LIBERACAO = 'U'
               AND IDEMPRESA = NEW_ROW.IDEMPRESA
               AND IDCENTRORESULTADO = NEW_ROW.IDCENTRORESULTADO
               AND IDCTACONTABIL = NEW_ROW.IDCTACONTABIL
               AND VALLANCAMENTO = NEW_ROW.VALLANCAMENTO
               AND MONTH(DTMOVIMENTO) = MONTH(NEW_ROW.DTMOVIMENTO)
               AND YEAR(DTMOVIMENTO)  = YEAR(NEW_ROW.DTMOVIMENTO)
       );

END@


-- =====================================================================
-- TESTE RÁPIDO (depois de criar tudo)
-- =====================================================================
--
-- 1. Tenta um lançamento que vai estourar previsto (no ERP)
-- 2. Confirma que o erro foi para ERRO_SISTEMA:
--    SELECT * FROM DBA.ERRO_SISTEMA WHERE NUMERRO = -438 ORDER BY DTERRO DESC FETCH FIRST 1 ROWS ONLY@
-- 3. Confirma que a solicitação foi criada automaticamente:
--    SELECT * FROM INTEGRIM.SOLICITACAO_LIBERACAO ORDER BY IDSOLICITACAO DESC FETCH FIRST 1 ROWS ONLY@
-- 4. Aprovar manualmente para teste:
--    UPDATE INTEGRIM.SOLICITACAO_LIBERACAO
--       SET FLAG_STATUS = 'A', TIPO_LIBERACAO = 'U',
--           USUARIO_APROVADOR = 'TESTE', DT_DECISAO = CURRENT_TIMESTAMP,
--           OBSERVACAO = 'Teste manual'
--     WHERE IDSOLICITACAO = <id-da-solicitação>@
-- 5. Refazer o lançamento no ERP — deve passar
-- 6. Verificar que foi consumida:
--    SELECT FLAG_STATUS FROM INTEGRIM.SOLICITACAO_LIBERACAO WHERE IDSOLICITACAO = <id>@
--    (deve estar 'U' = usada)
