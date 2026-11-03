# Conectar o Instagram

Com o [app da Meta](./app-meta) pronto:

1. Entre no seu painel e clique em **Conectar Instagram**.
2. A Meta abre pedindo autorização.
   - **Login unificado (app novo):** entre com o Facebook (ou com o Instagram), escolha o **portfólio que é dono da conta**, marque a **conta do Instagram**, deixe a conta de anúncios em branco e clique em **Confirmar**. A Meta pode pedir um código por SMS ou e-mail. No fim aparece "A empresa ... foi conectada": clique em **Concluir**.
   - **Login do Instagram (app antigo):** entre com a conta profissional que você adicionou como testadora e autorize.
3. Você volta para o painel com a conta conectada: aparecem o @ e a foto.

Se você liberou mais de uma conta do Instagram na tela da Meta, o painel pergunta qual delas esta instalação vai atender.

<!-- PRINT: tela de autorização da Meta listando as permissões pedidas -->
<Print>Tela de autorização da Meta listando as permissões pedidas.</Print>

## O que acontece por trás

- **Login unificado:** o acesso é da empresa (do portfólio), não da pessoa que clicou. Com validade "Nunca" na configuração, não vence e não precisa renovar. O painel mostra "acesso sem prazo de validade".
- **Login do Instagram:** a instância troca a autorização por um acesso de 60 dias e renova sozinha antes de vencer.
- Nos dois, ela liga a conta aos eventos que usa: comentários, comentários em live, mensagens e cliques em botão.
- Cada instalação atende **uma conta** do Instagram. Para duas contas, suba duas instalações.
- Quem já estava conectado pelo login do Instagram e reconecta pelo unificado continua com os mesmos fluxos, leads e histórico.

## Se der erro

| Mensagem | O que fazer |
|---|---|
| The following business assets were not granted the requested permissions | Você escolheu um portfólio que só tem a conta **compartilhada**. Conecte de novo escolhendo o portfólio **dono** da conta ([passo 7 do app](./app-meta#_7-conecte-a-conta-e-teste)). |
| Nenhuma conta profissional do Instagram veio junto | Na tela da Meta, escolha o portfólio certo e marque a conta. Se ela não aparece: a conta precisa ser Profissional (Empresa ou Criador) e pertencer a esse portfólio. |
| Invalid Scopes / Invalid platform app | O app é novo e o painel está em **Login do Instagram**. Em Configurações, marque **Login unificado** e preencha o ID da configuração. |
| A opção de entrar com o Instagram não aparece | O navegador já está logado no Facebook. Use **Adicionar outra conta** na tela da Meta, ou entre pelo Facebook mesmo. |
| Função de desenvolvedor é insuficiente | (App antigo) Você não aceitou o convite de testador. Veja [Se seu app é antigo](./app-meta#se-seu-app-e-antigo-login-do-instagram). |
| Erro de redirecionamento ou URI inválida | A URL de redirecionamento (na configuração do login unificado, ou em "Configurar o login da empresa" no app antigo) tem que ser exatamente `https://SEU-ENDERECO/auth/callback`, e o `BASE_URL` tem que ser o mesmo endereço, sem barra no fim. |
| Comentário chega e é respondido, mas a resposta da pessoa e o clique no botão não chegam | A conta não é **Testadora do Instagram** do app, ou não aceitou o convite ([passo 5 do app](./app-meta#_5-vire-testador-do-seu-proprio-app)). Confira também **Permitir acesso às mensagens** no Instagram ([passo 6](./app-meta#_6-publique-o-app)). |
| Comentário de seguidor não chega (nada no painel) | O app não está publicado ([passo 6 do app](./app-meta#_6-publique-o-app)). |
| Os eventos da Meta estão sendo recusados | Falta a chave secreta. [Passo 3 do app](./app-meta#_3-copie-o-id-e-a-chave-secreta). |
| Mensagens não saem: "disabled access to Instagram Direct Messaging" | No app do Instagram: **Configurações → Mensagens e respostas ao story → Controles de mensagem → Ferramentas conectadas → Permitir acesso às mensagens**. |

Se o painel mostrar **Reconectar conta**, o acesso venceu ou foi derrubado (no login unificado isso acontece se o app sair do portfólio ou a conta mudar de portfólio). Clique e autorize de novo; seus fluxos e leads continuam lá.

## Próximo passo

[Monte o primeiro fluxo](./primeiro-fluxo).
