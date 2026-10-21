# Conectar o Instagram

Com o [app da Meta](./app-meta) pronto e publicado:

1. Entre no seu painel e clique em **Conectar Instagram**.
2. O Instagram abre pedindo autorização. Entre com a conta profissional que você adicionou como testadora e autorize.
3. Você volta para o painel com a conta conectada: aparecem o @, a foto e quantos dias faltam para o acesso vencer.

<!-- PRINT: tela de autorização do Instagram listando as permissões pedidas -->
<Print>Tela de autorização do Instagram listando as permissões pedidas.</Print>

## O que acontece por trás

- A instância troca a autorização por um acesso de 60 dias e renova sozinha antes de vencer. Você não precisa reconectar.
- Ela assina os eventos que usa: comentários, comentários em live, mensagens e cliques em botão.
- Cada instalação atende **uma conta** do Instagram. Para duas contas, suba duas instalações.

## Se der erro

| Mensagem | O que fazer |
|---|---|
| Função de desenvolvedor é insuficiente | Você não aceitou o convite de testador. Volte ao [passo 4 do app](./app-meta#_4-vire-testador-do-seu-proprio-app). |
| Erro de redirecionamento ou URI inválida | A URI em "Configurar o login da empresa" tem que ser exatamente `https://SEU-ENDERECO/auth/callback`, e o `BASE_URL` tem que ser o mesmo endereço, sem barra no fim. |
| Os eventos da Meta estão sendo recusados | Falta a chave secreta do app do Instagram. [Passo 3 do app](./app-meta#_3-copie-o-id-e-a-chave-secreta). |

Se o painel mostrar **Reconectar conta**, o acesso venceu ou foi revogado no Instagram. Clique e autorize de novo; seus fluxos e leads continuam lá.

## Próximo passo

[Monte o primeiro fluxo](./primeiro-fluxo).
