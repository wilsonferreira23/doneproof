# DoneProof

DoneProof ajuda o Codex a não dizer “pronto” cedo demais.

Quando você pede uma mudança, não basta o agente escrever código ou um comando
terminar sem erro. A tarefa só é considerada concluída quando existe uma prova
executável de que o resultado pedido realmente aconteceu.

## Em poucas palavras

Imagine que você pediu:

> “Quem não estiver logado deve ser levado para `/login` ao abrir o painel.”

Sem DoneProof, o agente pode criar um arquivo de autenticação e concluir que
está tudo certo. Com DoneProof, ele precisa testar o comportamento de verdade:

```text
abrir /dashboard sem estar logado
↓
receber redirecionamento para /login
↓
registrar a evidência
↓
só então dizer que terminou
```

## Como funciona

Antes de alterar o projeto, o Codex cria uma pequena lista chamada **contrato de
sucesso**. Nela ficam as coisas que precisam ser verdade no final do trabalho.

Por exemplo:

```text
- a página redireciona quem não está logado
- os testes de autenticação passam
- o projeto continua compilando
```

Essa lista é bloqueada antes da implementação começar. Assim, se um teste
falhar, o agente não pode simplesmente diminuir a exigência para conseguir
marcar a tarefa como feita.

Depois da alteração, o verificador roda as provas combinadas e devolve um
resultado claro.

| Resultado | Significado |
| --- | --- |
| `VERIFIED_SUCCESS` | Tudo que foi combinado passou. |
| `VERIFIED_PARTIAL` | Parte passou, mas ainda falta algo. |
| `FAILED` | O resultado observado é diferente do esperado. |
| `BLOCKED` | Não foi possível testar por uma limitação externa. |

Somente `VERIFIED_SUCCESS` permite dizer que o trabalho terminou.

## Instalação

Copie a pasta desta skill para o local onde o Codex guarda suas skills:

```text
~/.codex/skills/doneproof/
```

Se quiser usar apenas em um projeto, coloque-a aqui:

```text
<seu-projeto>/.agents/skills/doneproof/
```

Você também pode copiar as orientações de
[`AGENTS.example.md`](AGENTS.example.md) para o `AGENTS.md` do projeto. Isso
faz o Codex lembrar de verificar cada etapa importante.

## Primeiro uso

1. Antes de mudar o código, crie `.proof-of-done/contract.json`.
2. Descreva nesse arquivo as provas que a tarefa precisa passar. Há um
   [exemplo pronto](examples/.proof-of-done/contract.json).
3. Bloqueie o contrato:

   ```bash
   python3 .agents/skills/doneproof/scripts/pod.py lock .proof-of-done/contract.json
   ```

4. Faça a alteração no projeto.
5. Rode a verificação da etapa:

   ```bash
   python3 .agents/skills/doneproof/scripts/pod.py verify .proof-of-done/contract.json --gate task-auth-redirect
   ```

O resultado fica salvo em `.proof-of-done/ledger.json`. Ele é um registro
local do que foi testado e do que aconteceu.

## Que tipos de prova ele entende?

DoneProof foi feito para ser simples e não exige bibliotecas extras. Ele tem
três tipos de prova:

| Tipo | Serve para |
| --- | --- |
| `command` | Rodar os testes, o build ou um comando que seu projeto já usa. |
| `file` | Confirmar que um arquivo existe ou contém algo esperado. |
| `http` | Abrir uma URL e conferir a resposta, como um redirecionamento. |

Para outras situações, use `command` para chamar a ferramenta que já existe no
seu projeto. DoneProof não tenta substituir seu sistema de testes.

## Um exemplo de prova

Este trecho diz: “ao abrir o painel, a resposta deve ser um redirecionamento
para a página de login”.

```json
{
  "id": "redireciona-sem-login",
  "type": "http",
  "url": "http://localhost:3000/dashboard",
  "expect_status": 302,
  "expect_headers": { "location": "/login" }
}
```

Isso é melhor do que apenas conferir se existe um arquivo chamado
`middleware`: ele testa o que a pessoa usando o sistema realmente vê.

## Ideias principais

- **Não aceite “confia em mim”.** O resumo de outro agente não é uma prova.
- **Depois de mudar algo, confira o resultado.** Criou um registro? Leia-o de
  volta. Publicou uma página? Abra a página.
- **Se falhar, conserte — não baixe a régua.** O contrato continua o mesmo até
  a tarefa passar.
- **Teste só o que importa.** Não é preciso rodar tudo a cada pequena mudança.

## Organização do repositório

```text
SKILL.md                         Instruções que o Codex segue
scripts/pod.py                   Programa que executa as provas
examples/.proof-of-done/         Exemplo de contrato de sucesso
AGENTS.example.md                Texto opcional para AGENTS.md
```

## Licença

Este projeto ainda não tem uma licença. Escolha uma antes de distribuir o
código ou aceitar contribuições externas.

## Fontes e referências

Estes dois papers são a fundamentação científica da DoneProof:

- [From Confident Closing to Silent Failure: Characterizing False Success in
  LLM Agents](https://arxiv.org/abs/2606.09863) (2026), de Laksh Advani — a
  base conceitual principal. O trabalho caracteriza o problema de *false
  success*: o agente afirma que terminou, mas o estado real do sistema mostra
  que a tarefa falhou. Ele também reforça que raciocinar ou pedir a opinião de
  outro LLM não substitui uma verificação do resultado observado.
- [Real-Time Detection and Repair of LLM Agent
  Failures](https://arxiv.org/abs/2608.02464) (2026), de Sunny Dubey — o
  reforço arquitetural. Ele inspira a direção de verificação determinística,
  confirmação das ações necessárias e o ciclo de verificar, detectar falha,
  reparar e verificar novamente.

DoneProof **não é uma implementação direta** desses papers. Ela é uma
**adaptação prática** dessas ideias para coding agents e Codex. Elementos como
o contrato de sucesso, o bloqueio SHA-256, os gates de tarefa/feature/milestone
e o estado `VERIFIED_SUCCESS` são a arquitetura criada neste projeto para uso
em looping engineering.
