1. Introdução e Pré-requisitos 
O SDK Admin do Firebase para Python permite que desenvolvedores acessem os 
serviços do Firebase a partir de ambientes privilegiados. Diferente dos SDKs de cliente, 
o SDK Admin possui privilégios totais de leitura e gravação em todos os dados do 
projeto. Antes de começar, é necessário possuir um projeto configurado no Console do 
Firebase e um ambiente de desenvolvimento Python funcional. 

 
2. Instalação do SDK 
A instalação é simples e feita via PIP (Python Package Index). Dependendo do seu 
ambiente, utilize um dos comandos abaixo: 
- Instalação Global (requer sudo): sudo pip install firebase-admin 
- Instalação Local (apenas para o usuário atual): pip install --user firebase-admin 

 
3. Estratégias de Inicialização 
A forma como o SDK é inicializado depende do local onde o código está sendo 
executado. O Firebase oferece suporte a diferentes métodos de autenticação para 
garantir a segurança e a facilidade de integração. 

 
3.1 Ambientes do Google Cloud 
Para aplicações rodando no Google Cloud (como App Engine, Cloud Functions ou 
Cloud Run), recomenda-se o uso das Application Default Credentials (ADC). O 
processo é automático e não requer chaves manuais. 
Código de exemplo: 
import firebase_admin 
firebase_admin.initialize_app() 

 
3.2 Ambientes Fora do Google (Servidores Locais/Próprios) 
Em ambientes externos, você deve usar um arquivo de chave JSON da conta de 
serviço. Para obter este arquivo, siga estas etapas no Console do Firebase: 

1. Acesse Configurações do Projeto > Contas de Serviço. 
2. Clique em "Gerar nova chave privada". 
3. Salve o arquivo JSON gerado em um local seguro. 

A melhor prática é definir a variável de ambiente 
GOOGLE_APPLICATION_CREDENTIALS apontando para este arquivo, permitindo que 
o SDK detecte as credenciais automaticamente 

 

4. Autenticação Avançada 
Além das credenciais padrão, o SDK suporta autenticação via Tokens de Atualização 
OAuth 2.0. Isso é útil em fluxos de delegação de acesso, embora não seja compatível 
com o Cloud Firestore. 

 
5. Gerenciamento de Múltiplos Aplicativos 
Em cenários onde é necessário interagir com múltiplos projetos do Firebase na mesma 
aplicação, o SDK permite a criação de instâncias nomeadas. Isso possibilita isolar 
configurações e permissões para cada projeto separadamente. 

 
6. Capacidades do SDK Admin 
Uma vez inicializado, o SDK Admin fornece acesso a uma vasta gama de serviços 
administrativos: 
Gerenciamento de Usuários: Criação, edição e exclusão de contas, além de 
gerenciamento de tokens de autenticação personalizada. 
- Realtime Database e Firestore: Operações de CRUD (Criar, Ler, Atualizar, Deletar) 
com permissões totais sobre os dados. 
- Firebase Cloud Messaging (FCM): Envio de notificações push e mensagens de 
dados para dispositivos móveis e web. 
- Cloud Storage: Upload e download de arquivos, além de geração de URLs 
assinadas para acesso temporário. 
- Remote Config e Segurança: Atualização programática de configurações remotas e 
regras de segurança do banco de dados. 
 

 
