-- =====================================================================
-- Function otimizada para a tela DRE.
--
-- Diferenças em relação a UF_CENTRORESULTADOS:
--   1. Aceita filtro de MÊS inicial e final (não precisa puxar o ano todo).
--   2. WHERE com DTMOVIMENTO usando range (BETWEEN >= < ) em vez de YEAR(),
--      o que permite o otimizador usar índice em DTMOVIMENTO.
--   3. Bloco 3 (config sem movimento): NOT EXISTS único, cobrindo ambos os
--      anos via range de data (eliminação da subquery redundante).
--
-- Mantém o mesmo SHAPE de retorno da function original — pode ser
-- exposta no CISS-Poder com endpoint "centro_resultado_bi_dre" (ou outro
-- nome de sua escolha; o Python aceita configurar).
-- =====================================================================

CREATE OR REPLACE FUNCTION INTEGRIM.UF_CENTRORESULTADOS_DRE (
    AnoReferencia            INT,
    IdEmpresaFiltro          INT DEFAULT NULL,
    IdCentroResultadoFiltro  INT DEFAULT NULL,
    MesInicial               INT DEFAULT NULL,
    MesFinal                 INT DEFAULT NULL
)
RETURNS TABLE (IDEMPRESA INT, EMPRESA VARCHAR(255),
               IDCENTRORESULTADO INT, DESCRCENTRORESULTADO VARCHAR(255),
               CENTRO_RESULTADOS VARCHAR(255),
               IDCTACONTABIL INT, DESCRCTACONTABIL VARCHAR(255),
               CONTABIL VARCHAR(255),
               VALOR_REALIZADO DECIMAL(15, 6),
               ANO_ANTERIOR DECIMAL(15, 6),
               VALOR_PREVISTO DECIMAL(15, 6),
               MES_ANO VARCHAR(7),
               MESDESC VARCHAR(20),
               MES_CORR VARCHAR(10),
               MES_ANTERIOR INT, MES_ATUAL INT, ANO INT, MES_NUM INT)
RETURN
 (
  SELECT SA.IDEMPRESA,
         EMPRESA,
         SA.IDCENTRORESULTADO,
         DESCRCENTRORESULTADO,
         CENTRO_RESULTADOS,
         SA.IDCTACONTABIL,
         DESCRCTACONTABIL,
         CONTABIL,
         SUM(VALOR_REALIZADO) AS VALOR_REALIZADO,
         SUM(COALESCE(ANO_ANTERIOR, 0)) AS ANO_ANTERIOR,
         CAST(SUM(CASE
                     WHEN SA.ANO_ANTERIOR IS NULL THEN C.VALORPREVISAO
                     ELSE CASE
                              WHEN (C.IDEEMPPREVISAO IS NULL OR C.IDEEMPPREVISAO = 0 OR SA.IDEMPRESA = C.IDEEMPPREVISAO)
                                   AND (C.IDCENTRORESULTADO IS NULL OR C.IDCENTRORESULTADO = 0 OR SA.IDCENTRORESULTADO = C.IDCENTRORESULTADO)
                                   AND (C.IDCTACONTABIL IS NULL OR C.IDCTACONTABIL = 0 OR SA.IDCTACONTABIL = C.IDCTACONTABIL)
                                   AND (C.MESPREVISAO IS NULL OR C.MESPREVISAO = 0 OR SA.MES_ANTERIOR = C.MESPREVISAO) THEN
                                  CASE C.TIPOPREVISAO
                                      WHEN 'P' THEN (COALESCE(ANO_ANTERIOR, 0) + (COALESCE(ANO_ANTERIOR, 0) * C.VALORPREVISAO / 100.0))
                                      WHEN 'V' THEN C.VALORPREVISAO
                                      ELSE (COALESCE(ANO_ANTERIOR, 0) - (COALESCE(ANO_ANTERIOR, 0) * 5) / 100.0)
                                  END
                              ELSE (COALESCE(ANO_ANTERIOR, 0) - (COALESCE(ANO_ANTERIOR, 0) * 5) / 100.0)
                          END
                 END) AS DECIMAL(15, 6)) AS VALOR_PREVISTO,
         MES_ANO, MESDESC, MES_CORR, MES_ANTERIOR, MES_ATUAL, ANO, MES_NUM
  FROM
      (
       -- ===========================================================
       -- BLOCO 1: Dados do Ano Atual
       -- (range em DTMOVIMENTO permite uso de índice)
       -- ===========================================================
       SELECT CRM.IDEMPRESA,
              CAST(CRM.IDEMPRESA AS VARCHAR(10)) || ' - ' || E.NOMEFANTASIA AS EMPRESA,
              CRM.IDCENTRORESULTADO,
              CR.DESCRCENTRORESULTADO,
              CAST(CRM.IDCENTRORESULTADO AS VARCHAR(10)) || ' - ' || CR.DESCRCENTRORESULTADO AS CENTRO_RESULTADOS,
              CRM.IDCTACONTABIL,
              CPC.DESCRCTACONTABIL,
              CAST(CRM.IDCTACONTABIL AS VARCHAR(10)) || ' - ' || CPC.DESCRCTACONTABIL AS CONTABIL,
              SUM(CASE
                      WHEN CPC.TIPONATUREZA = 'D' AND CRM.TIPONATUREZALCTO = 'D' THEN CRM.VALLANCAMENTO
                      WHEN CPC.TIPONATUREZA = 'D' AND CRM.TIPONATUREZALCTO = 'C' THEN CRM.VALLANCAMENTO * -1
                      WHEN CPC.TIPONATUREZA = 'C' AND CRM.TIPONATUREZALCTO = 'C' THEN CRM.VALLANCAMENTO
                      WHEN CPC.TIPONATUREZA = 'C' AND CRM.TIPONATUREZALCTO = 'D' THEN CRM.VALLANCAMENTO * -1
                      ELSE 0
                  END) AS VALOR_REALIZADO,
              0 AS ANO_ANTERIOR,
              LPAD(MONTH(CRM.DTMOVIMENTO), 2, '0') || '/' || YEAR(CRM.DTMOVIMENTO) AS MES_ANO,
              CAST(NULL AS VARCHAR(20)) AS MESDESC,
              CASE MONTH(CRM.DTMOVIMENTO) WHEN 1 THEN 'Janeiro' WHEN 2 THEN 'Fevereiro' WHEN 3 THEN 'Março' WHEN 4 THEN 'Abril' WHEN 5 THEN 'Maio' WHEN 6 THEN 'Junho' WHEN 7 THEN 'Julho' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Setembro' WHEN 10 THEN 'Outubro' WHEN 11 THEN 'Novembro' WHEN 12 THEN 'Dezembro' ELSE 'Mês Inválido' END AS MES_CORR,
              MONTH(CRM.DTMOVIMENTO) AS MES_ATUAL,
              NULL AS MES_ANTERIOR,
              YEAR(CRM.DTMOVIMENTO) AS ANO,
              MONTH(CRM.DTMOVIMENTO) AS MES_NUM
       FROM DBA.CENTRO_RESULTADO AS CR,
            DBA.CONTABIL_PLANO_CONTAS AS CPC,
            DBA.CENTRO_RESULTADO_MOVIMENTO AS CRM,
            DBA.EMPRESA AS E
       WHERE CR.IDCENTRORESULTADO = CRM.IDCENTRORESULTADO
         AND CPC.IDCTACONTABIL = CRM.IDCTACONTABIL
         AND CRM.IDEMPRESA = E.IDEMPRESA
         AND CRM.TIPOREGIME = 'C'
         -- ⚡ range em DTMOVIMENTO em vez de YEAR(): usa índice
         AND CRM.DTMOVIMENTO >= DATE(AnoReferencia || '-01-01')
         AND CRM.DTMOVIMENTO <  DATE((AnoReferencia + 1) || '-01-01')
         AND (MesInicial IS NULL OR MONTH(CRM.DTMOVIMENTO) >= MesInicial)
         AND (MesFinal   IS NULL OR MONTH(CRM.DTMOVIMENTO) <= MesFinal)
         AND (IdEmpresaFiltro IS NULL OR IdEmpresaFiltro = 0 OR CRM.IDEMPRESA = IdEmpresaFiltro)
         AND (IdCentroResultadoFiltro IS NULL OR IdCentroResultadoFiltro = 0 OR CRM.IDCENTRORESULTADO = IdCentroResultadoFiltro)
       GROUP BY CRM.IDEMPRESA, CRM.IDCENTRORESULTADO, CR.DESCRCENTRORESULTADO,
                CRM.IDCTACONTABIL, CPC.DESCRCTACONTABIL, CPC.TIPONATUREZA,
                E.NOMEFANTASIA, YEAR(CRM.DTMOVIMENTO), MONTH(CRM.DTMOVIMENTO)

       UNION ALL

       -- ===========================================================
       -- BLOCO 2: Dados do Ano Anterior
       -- (apenas os meses dentro do range de filtro)
       -- ===========================================================
       SELECT SA.IDEMPRESA,
              CAST(SA.IDEMPRESA AS VARCHAR(10)) || ' - ' || E.NOMEFANTASIA AS EMPRESA,
              SA.IDCENTRORESULTADO,
              CR.DESCRCENTRORESULTADO,
              CAST(SA.IDCENTRORESULTADO AS VARCHAR(10)) || ' - ' || CR.DESCRCENTRORESULTADO AS CENTRO_RESULTADOS,
              SA.IDCTACONTABIL,
              CPC.DESCRCTACONTABIL,
              CAST(SA.IDCTACONTABIL AS VARCHAR(10)) || ' - ' || CPC.DESCRCTACONTABIL AS CONTABIL,
              0 AS VALOR_REALIZADO,
              SUM(CASE
                      WHEN CPC.TIPONATUREZA = 'D' AND CRM.TIPONATUREZALCTO = 'D' THEN CRM.VALLANCAMENTO
                      WHEN CPC.TIPONATUREZA = 'D' AND CRM.TIPONATUREZALCTO = 'C' THEN CRM.VALLANCAMENTO * -1
                      WHEN CPC.TIPONATUREZA = 'C' AND CRM.TIPONATUREZALCTO = 'C' THEN CRM.VALLANCAMENTO
                      WHEN CPC.TIPONATUREZA = 'C' AND CRM.TIPONATUREZALCTO = 'D' THEN CRM.VALLANCAMENTO * -1
                      ELSE 0
                  END) AS ANO_ANTERIOR,
              LPAD(M.Mes, 2, '0') || '/' || (AnoReferencia - 1) AS MES_ANO,
              CAST(NULL AS VARCHAR(20)) AS MESDESC,
              CASE M.Mes WHEN 1 THEN 'Janeiro' WHEN 2 THEN 'Fevereiro' WHEN 3 THEN 'Março' WHEN 4 THEN 'Abril' WHEN 5 THEN 'Maio' WHEN 6 THEN 'Junho' WHEN 7 THEN 'Julho' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Setembro' WHEN 10 THEN 'Outubro' WHEN 11 THEN 'Novembro' WHEN 12 THEN 'Dezembro' ELSE 'Mês Inválido' END AS MES_CORR,
              NULL AS MES_ATUAL,
              M.Mes AS MES_ANTERIOR,
              (AnoReferencia - 1) AS ANO,
              M.Mes AS MES_NUM
       FROM (-- ⚡ Só gera os meses do range solicitado
             SELECT MES FROM (VALUES (1),(2),(3),(4),(5),(6),(7),(8),(9),(10),(11),(12)) AS V(MES)
             WHERE (MesInicial IS NULL OR V.MES >= MesInicial)
               AND (MesFinal   IS NULL OR V.MES <= MesFinal)
            ) AS M(Mes)
       CROSS JOIN
           (SELECT DISTINCT IDEMPRESA, IDCENTRORESULTADO, IDCTACONTABIL
            FROM DBA.CENTRO_RESULTADO_MOVIMENTO
            -- ⚡ range em vez de YEAR()
            WHERE DTMOVIMENTO >= DATE((AnoReferencia - 1) || '-01-01')
              AND DTMOVIMENTO <  DATE(AnoReferencia || '-01-01')
              AND (IdEmpresaFiltro IS NULL OR IdEmpresaFiltro = 0 OR IDEMPRESA = IdEmpresaFiltro)
              AND (IdCentroResultadoFiltro IS NULL OR IdCentroResultadoFiltro = 0 OR IDCENTRORESULTADO = IdCentroResultadoFiltro)) AS SA
       LEFT JOIN DBA.CENTRO_RESULTADO_MOVIMENTO AS CRM ON CRM.IDEMPRESA = SA.IDEMPRESA
         AND CRM.IDCENTRORESULTADO = SA.IDCENTRORESULTADO
         AND CRM.IDCTACONTABIL = SA.IDCTACONTABIL
         AND CRM.TIPOREGIME = 'C'
         AND CRM.DTMOVIMENTO >= DATE((AnoReferencia - 1) || '-01-01')
         AND CRM.DTMOVIMENTO <  DATE(AnoReferencia || '-01-01')
         AND MONTH(CRM.DTMOVIMENTO) = M.Mes
       LEFT JOIN DBA.CENTRO_RESULTADO AS CR ON CR.IDCENTRORESULTADO = SA.IDCENTRORESULTADO
       LEFT JOIN DBA.CONTABIL_PLANO_CONTAS AS CPC ON CPC.IDCTACONTABIL = SA.IDCTACONTABIL
       LEFT JOIN DBA.EMPRESA AS E ON E.IDEMPRESA = SA.IDEMPRESA
       GROUP BY SA.IDEMPRESA, SA.IDCENTRORESULTADO, CR.DESCRCENTRORESULTADO,
                SA.IDCTACONTABIL, CPC.DESCRCTACONTABIL, CPC.TIPONATUREZA,
                E.NOMEFANTASIA, (AnoReferencia - 1), M.Mes

       UNION ALL

       -- ===========================================================
       -- BLOCO 3: Configurações de Previsão Sem Movimentação
       -- (NOT EXISTS único — abrange ambos os anos via range)
       -- ===========================================================
       SELECT C.IDEEMPPREVISAO AS IDEMPRESA,
              CAST(C.IDEEMPPREVISAO AS VARCHAR(10)) || ' - ' || E.NOMEFANTASIA AS EMPRESA,
              C.IDCENTRORESULTADO,
              CR.DESCRCENTRORESULTADO,
              CAST(C.IDCENTRORESULTADO AS VARCHAR(10)) || ' - ' || CR.DESCRCENTRORESULTADO AS CENTRO_RESULTADOS,
              C.IDCTACONTABIL,
              CPC.DESCRCTACONTABIL,
              CAST(C.IDCTACONTABIL AS VARCHAR(10)) || ' - ' || CPC.DESCRCTACONTABIL AS CONTABIL,
              0 AS VALOR_REALIZADO,
              NULL AS ANO_ANTERIOR,
              LPAD(C.MESPREVISAO, 2, '0') || '/' || (AnoReferencia - 1) AS MES_ANO,
              CAST(NULL AS VARCHAR(20)) AS MESDESC,
              CASE C.MESPREVISAO WHEN 1 THEN 'Janeiro' WHEN 2 THEN 'Fevereiro' WHEN 3 THEN 'Março' WHEN 4 THEN 'Abril' WHEN 5 THEN 'Maio' WHEN 6 THEN 'Junho' WHEN 7 THEN 'Julho' WHEN 8 THEN 'Agosto' WHEN 9 THEN 'Setembro' WHEN 10 THEN 'Outubro' WHEN 11 THEN 'Novembro' WHEN 12 THEN 'Dezembro' ELSE 'Mês Inválido' END AS MES_CORR,
              NULL AS MES_ATUAL,
              C.MESPREVISAO AS MES_ANTERIOR,
              (AnoReferencia - 1) AS ANO,
              C.MESPREVISAO AS MES_NUM
       FROM INTEGRIM.CENTRO_RESULTADO_CONFIG AS C
       LEFT JOIN DBA.EMPRESA AS E ON E.IDEMPRESA = C.IDEEMPPREVISAO
       LEFT JOIN DBA.CENTRO_RESULTADO AS CR ON CR.IDCENTRORESULTADO = C.IDCENTRORESULTADO
       LEFT JOIN DBA.CONTABIL_PLANO_CONTAS AS CPC ON CPC.IDCTACONTABIL = C.IDCTACONTABIL
       WHERE C.ANOCADASTRO = AnoReferencia
         AND C.IDEEMPPREVISAO IS NOT NULL
         AND C.IDCENTRORESULTADO IS NOT NULL
         AND C.IDCTACONTABIL IS NOT NULL
         AND (MesInicial IS NULL OR C.MESPREVISAO >= MesInicial)
         AND (MesFinal   IS NULL OR C.MESPREVISAO <= MesFinal)
         AND (IdEmpresaFiltro IS NULL OR IdEmpresaFiltro = 0 OR C.IDEEMPPREVISAO = IdEmpresaFiltro)
         AND (IdCentroResultadoFiltro IS NULL OR IdCentroResultadoFiltro = 0 OR C.IDCENTRORESULTADO = IdCentroResultadoFiltro)
         -- ⚡ um único NOT EXISTS cobrindo ambos os anos via range
         AND NOT EXISTS (
             SELECT 1
             FROM DBA.CENTRO_RESULTADO_MOVIMENTO AS CRM
             WHERE CRM.IDEMPRESA = C.IDEEMPPREVISAO
               AND CRM.IDCENTRORESULTADO = C.IDCENTRORESULTADO
               AND CRM.IDCTACONTABIL = C.IDCTACONTABIL
               AND CRM.DTMOVIMENTO >= DATE((AnoReferencia - 1) || '-01-01')
               AND CRM.DTMOVIMENTO <  DATE((AnoReferencia + 1) || '-01-01')
         )
      ) AS SA
  LEFT JOIN INTEGRIM.CENTRO_RESULTADO_CONFIG C
    ON (C.IDEEMPPREVISAO IS NULL OR C.IDEEMPPREVISAO = SA.IDEMPRESA)
   AND (C.IDCENTRORESULTADO IS NULL OR C.IDCENTRORESULTADO = SA.IDCENTRORESULTADO)
   AND (C.IDCTACONTABIL IS NULL OR C.IDCTACONTABIL = SA.IDCTACONTABIL)
   AND (C.MESPREVISAO IS NULL OR C.MESPREVISAO = SA.MES_ANTERIOR)
   AND C.ANOCADASTRO = AnoReferencia
  GROUP BY IDEMPRESA, EMPRESA, SA.IDCENTRORESULTADO, DESCRCENTRORESULTADO,
           CENTRO_RESULTADOS, SA.IDCTACONTABIL, DESCRCTACONTABIL, CONTABIL,
           MES_ANO, MESDESC, MES_CORR, MES_ANTERIOR, MES_ATUAL, ANO, MES_NUM
 );

-- =====================================================================
-- ÍNDICES RECOMENDADOS (caminho 2)
-- Rode UMA VEZ. Se já existirem com nomes parecidos, pule.
-- =====================================================================

-- Cobre o filtro principal: range de DTMOVIMENTO + TIPOREGIME
CREATE INDEX DBA.IX_CRM_DT_REGIME
  ON DBA.CENTRO_RESULTADO_MOVIMENTO (DTMOVIMENTO, TIPOREGIME);

-- Cobre os JOINs por chave de negócio + range de data
CREATE INDEX DBA.IX_CRM_CHAVE_DT
  ON DBA.CENTRO_RESULTADO_MOVIMENTO
     (IDEMPRESA, IDCENTRORESULTADO, IDCTACONTABIL, DTMOVIMENTO);

-- Cobre o lookup do CONFIG por ano de cadastro
CREATE INDEX INTEGRIM.IX_CRC_ANOCAD
  ON INTEGRIM.CENTRO_RESULTADO_CONFIG
     (ANOCADASTRO, IDEEMPPREVISAO, IDCENTRORESULTADO, IDCTACONTABIL, MESPREVISAO);

-- Atualiza estatísticas para o otimizador escolher os índices novos
RUNSTATS ON TABLE DBA.CENTRO_RESULTADO_MOVIMENTO
  WITH DISTRIBUTION AND DETAILED INDEXES ALL;
RUNSTATS ON TABLE INTEGRIM.CENTRO_RESULTADO_CONFIG
  WITH DISTRIBUTION AND DETAILED INDEXES ALL;

-- =====================================================================
-- CADASTRO DO SERVIÇO NA TABELA INTEGRIM.SERVICO
--
-- Para descobrir o próximo ID (substitua <NOVO_ID> abaixo):
--
--   SELECT COALESCE(MAX(ID_SERVICO), 0) + 1 AS PROXIMO_ID
--   FROM INTEGRIM.SERVICO
--   WHERE ID_SERVICO < 10000;
--
-- Anote o valor retornado e troque os DOIS <NOVO_ID> no INSERT abaixo.
-- =====================================================================

INSERT INTO INTEGRIM.SERVICO
VALUES
(<NOVO_ID>, 'CENTRO_RESULTADO_BI_DRE', '/centro_resultado_bi_dre',
'SELECT IDEMPRESA,EMPRESA,IDCENTRORESULTADO,
     DESCRCENTRORESULTADO,CENTRO_RESULTADOS,IDCTACONTABIL,DESCRCTACONTABIL,CONTABIL,
     SUM(VALOR_REALIZADO) AS VALOR_REALIZADO,
     SUM(ANO_ANTERIOR) AS ANO_ANTERIOR,
     SUM(VALOR_PREVISTO) AS VALOR_PREVISTO,
     MES_CORR,
     MES_NUM
FROM
        TABLE(INTEGRIM.UF_CENTRORESULTADOS_DRE(:anoreferencia, :idempfiltro, :idcentroresultadofiltro, :mesinicial, :mesfinal))
 GROUP BY
         IDEMPRESA,EMPRESA,IDCENTRORESULTADO,
     DESCRCENTRORESULTADO,CENTRO_RESULTADOS,IDCTACONTABIL,DESCRCTACONTABIL,CONTABIL, MES_CORR,MES_NUM
ORDER BY MES_NUM ASC',
'SELECT', '<NOVO_ID>', 'F')
GO
COMMIT;
