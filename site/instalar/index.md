# Instalar

O comenta EU QUERO roda na sua máquina: um container Docker com um banco SQLite dentro. Escolha o caminho que combina com você.

::: tip Prefere com ajuda?
No [Push Club](https://ia.augustogobatto.com/club) tem aula de instalação do zero, fluxos prontos e um grupo pra tirar dúvida.
:::

| Caminho | Pra quem | O que você faz |
|---|---|---|
| [Chão, 1 comando](./chao) | Quem tem uma VPS e quer tudo pronto | Cola um comando. HTTPS, senha, backup e atualização vêm prontos. |
| [Docker manual](./docker) | Quem já usa Docker e quer controlar cada peça | Escreve o `docker-compose.yml` e o `.env`, põe um proxy com HTTPS na frente. |
| [Computador + Cloudflare Tunnel](./computador) | Quem quer testar sem pagar servidor | Roda no seu computador e expõe com um túnel grátis. |

## O que você precisa em qualquer caminho

- **Conta profissional no Instagram** (Empresa ou Criador de conteúdo). A troca é grátis, em Configurações do Instagram, Tipo de conta.
- **Um endereço HTTPS público.** A Meta só entrega eventos em HTTPS. Os três caminhos acima resolvem isso.
- **Um app seu na Meta.** É de graça e leva uns 20 minutos: [tutorial passo a passo](/tutoriais/app-meta).
- **Uma máquina ligada 24 horas** com Docker. Uma VPS de 1 GB de memória sobra. O processador precisa ser x86_64 (Intel ou AMD): ainda não existe imagem para ARM.

::: tip Quanto custa
O software não cobra nada. Uma VPS básica custa de R$ 20 a R$ 30 por mês nos provedores brasileiros. Se usar o seu computador, o custo é zero, mas ele precisa ficar ligado.
:::

## Depois de instalar

1. [Crie o app da Meta](/tutoriais/app-meta)
2. [Conecte o Instagram](/tutoriais/conectar-instagram)
3. [Monte o primeiro fluxo](/tutoriais/primeiro-fluxo)
