# Como eu desenharia isso em produção (notas, NÃO implementado)

Este arquivo é só intenção. Nada do que está abaixo existe no repositório.

1. **Trocar o modelo de regras por um LLM** com saída estruturada (JSON com esquema), validada no código antes
   de entrar no grafo. A interface é a mesma (`classificar`, `extrair_itens`, `responder_duvida`); o que muda
   é o custo, a latência e a variação de resposta, então cada caso do eval teria de rodar mais de uma vez.
2. **Juiz de LLM** (`GEval` do DeepEval ou equivalente) para o que regra não mede, como a clareza do texto
   devolvido ao engenheiro. Precisa de rubrica e de uma amostra rotulada por pessoa para medir a concordância
   do juiz com ela. Eu não rodei nenhum juiz.
3. **Langfuse com servidor próprio**: traces por mensagem, dataset com os casos do `eval/casos.json` e
   uma nota por caso e por métrica ligada ao trace. No repositório o rastreamento só liga se houver chaves, e eu
   não o executei contra um servidor.
4. **Checkpointer persistente** (Postgres) no lugar da memória, para a aprovação humana sobreviver a um
   reinício, e um tempo limite para pedidos pendentes.
5. **Conjunto de avaliação maior e de fora**: mensagens reais anonimizadas, escritas por mais de uma pessoa.
6. **Portão no CI**: a suíte de avaliação rodando a cada mudança, falhando se alguma métrica cair abaixo
   do combinado.
