# CTT Criar Lojas Online — Dashboard Executivo

Dashboard executivo com dados históricos 2020–2026, comparações período homólogo e análise de cohorts, alimentado em tempo real pela API do Intercom.

## Arquitectura

```
GitHub Pages (frontend)  ←  data.json (gerado automaticamente)
                                  ↑
                    GitHub Actions (cron horário)
                                  ↑
                          Intercom REST API
```

O frontend é 100% estático — não faz chamadas de API. O workflow do GitHub Actions corre de hora a hora, chama o Intercom, gera `data.json` e faz commit. O browser lê apenas esse ficheiro.

## Setup em 5 passos

### 1. Cria o repositório no GitHub
```bash
git clone https://github.com/<teu-user>/clo-dashboard.git
cd clo-dashboard
```

Ou usa o botão "Fork" se já tiveres este repositório como template.

### 2. Adiciona o token Intercom como Secret

1. No teu repositório GitHub → **Settings → Secrets and variables → Actions**
2. Clica **New repository secret**
3. Nome: `INTERCOM_TOKEN`
4. Valor: o teu token de acesso Intercom (encontras em Intercom → Settings → Integrations → API → Personal access tokens)

### 3. Activa GitHub Pages

1. **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / `(root)`
4. Guarda

O teu dashboard ficará disponível em: `https://<teu-user>.github.io/<repo-name>/`

### 4. Executa o workflow pela primeira vez

1. **Actions → Refresh CLO Dashboard Data → Run workflow**
2. Aguarda ~2 minutos
3. O `data.json` será gerado e commitado automaticamente

### 5. Acede ao dashboard

`https://<teu-user>.github.io/clo-dashboard/`

---

## Estrutura do projecto

```
clo-dashboard/
├── index.html                        # Dashboard (lê data.json)
├── data.json                         # Gerado pelo GitHub Actions
├── scripts/
│   └── fetch_data.py                 # Script Python de fetch Intercom
└── .github/
    └── workflows/
        └── refresh-data.yml          # Cron job horário
```

## O que o dashboard mostra

### Dados exactos (via Intercom Search API)
- Total de conversas por ano (2020–2026)
- Comparação Q1 período homólogo: Q1 2024 vs Q1 2025 vs Q1 2026

### Dados de funil (via Intercom tags)
- Total de lojas registadas
- Lojas com primeiro pagamento (tag `Has First Payment`)
- Lojas ativas (tag `Client-Active`)
- Conversas abertas em tempo real

### Análise de cohorts (amostra ~400 empresas, 7 páginas)
- GMV acumulado por cohort de registo
- Spend mensal médio por cohort
- Taxa de subscrição anual por cohort
- Taxa de conversão para primeiro pagamento
- Dias médios até primeiro pagamento

### Outros
- Distribuição por plano (Corporate, Corp+, Plus, Base)
- Top 10 indústrias
- Métodos de pagamento mais usados
- Top 15 lojas por receita CTT
- Conversas de suporte abertas (com preview)

## Atualização dos dados

O workflow corre automaticamente a cada hora. Podes também correr manualmente:
**Actions → Refresh CLO Dashboard Data → Run workflow**

Para alterar a frequência, edita o cron em `.github/workflows/refresh-data.yml`:
```yaml
- cron: "0 * * * *"   # de hora a hora
- cron: "0 9 * * *"   # uma vez por dia às 9h
```

## Desenvolvido por

CTT — Criar Lojas Online · Dashboard gerado com dados Intercom
