# RPG Soundboard

Um **soundboard leve para mestres de RPG de mesa**, desenvolvido em **Python + PyQt6 + VLC**, focado em rapidez durante sessões.
Permite tocar **trilhas de fundo em loop** e **efeitos sonoros momentâneos** com controle individual de volume, pausa e parada.

A aplicação foi projetada para ser **simples, rápida e confiável durante sessões ao vivo**, evitando menus complexos ou interações lentas.

---

# ✨ Funcionalidades

* 🎵 **Trilhas de fundo em loop**
* 🔊 **Efeitos sonoros simultâneos**
* 🎚 **Controle individual de volume**
* ⏯ **Pausar e retomar trilhas**
* ⏹ **Parar efeitos ou trilhas individualmente**
* 🧹 **Remoção automática de efeitos quando terminam**
* 📂 **Escolha de pastas de trilhas e efeitos**
* 💾 **Configuração persistente entre execuções**
* ⌨ **Atalhos de teclado otimizados para uso durante sessões**

---

# 📸 Interface

A interface é dividida em três áreas principais:

### 1️⃣ Trilhas

Lista de músicas de fundo.
Ao tocar uma trilha, ela entra automaticamente em **loop infinito**.

### 2️⃣ Efeitos

Lista de efeitos sonoros momentâneos.
Eles **tocam uma vez e desaparecem automaticamente quando terminam**.

### 3️⃣ Tocando agora

Lista de todos os sons ativos com controles:

* **⏸ Pausar / Retomar**
* **⏹ Parar**
* **Controle de volume individual**

---

# ⌨ Atalhos de Teclado

| Atalho       | Ação                                  |
|--------------|---------------------------------------|
| **Enter**    | Tocar item selecionado                |
| **Space**    | Pausar/retomar som selecionado        |
| **Delete**   | Parar som selecionado                 |
| **Ctrl + R** | Atualizar listas de trilhas e efeitos |
| **Ctrl + K** | Parar todos os sons                   |
| **Ctrl + T** | Escolher pasta de trilhas             |
| **Ctrl + E** | Escolher pasta de efeitos             |

---

# 📦 Estrutura do Projeto

```
rpg-soundboard/
├── main.py
├── .gitignore
├── .python-version
├── pyproject.toml
├── uv.lock
└── rpg-soundboard/
    ├── gui.py
    ├── sound_manager.py
    ├── widgets.py
    ├── config.py
    ├── utils.py
    └── ...
```

### main.py

Ponto de entrada da aplicação.

Responsável por:

* iniciar o `QApplication`
* abrir a janela principal.

---

### gui.py

Contém a **interface principal (`SoundboardWindow`)**.

Responsável por:

* layout da interface
* integração com `SoundManager`
* gerenciamento das listas
* atalhos de teclado
* criação dos widgets de reprodução.

---

### sound_manager.py

Camada de **controle de áudio**.

Responsável por:

* criar players VLC
* tocar trilhas ou efeitos
* parar sons
* limpar efeitos finalizados.

Isola completamente a lógica de áudio da interface.

---

### widgets.py

Contém **widgets reutilizáveis da interface**.

Atualmente inclui:

`PlayerItemWidget`

Widget que representa um som ativo com:

* nome
* botão de pausa
* botão de parada
* slider de volume.

---

### config.py

Responsável pela **persistência das configurações**.

Configuração armazenada em:

```
~/.rpg_soundboard_config.json
```

Exemplo:

```json
{
  "trilhas_dir": "/home/user/music/rpg/trilhas",
  "efeitos_dir": "/home/user/music/rpg/efeitos",
  "default_volume": 80
}
```

---

### utils.py

Funções utilitárias usadas pelo sistema.

Atualmente:

* detecção de arquivos de áudio suportados.

---

# 🔧 Requisitos

Python **3.9+** recomendado.

Dependências Python:

```
pip install PyQt6 python-vlc
```

Além disso é necessário ter o **VLC instalado no sistema**, pois o `python-vlc` utiliza a biblioteca **libVLC**.

---

# 📦 Gerenciamento de Dependências (recomendado: uv)

O projeto foi preparado para uso com uv (gestor moderno de ambientes/dependências):
* usa `pyproject.toml`
* gera/usa `uv.lock` para instalações reproduzíveis
* cria `.venv/` automaticamente quando necessário

---

# 🖥 Instalação com .venv

Clone o repositório:

```
git clone https://github.com/DiegoJohann/rpg-soundboard
cd rpg-soundboard
```

Crie um ambiente virtual:

```
python -m venv .venv
source .venv/bin/activate
```

Instale dependências:

```
pip install PyQt6 python-vlc
```

Execute:

```
python main.py
```

---

# 🖥 Instalação com uv

Instale o uv (Linux/macOS — script oficial):

```
curl -LsSf https://astral.sh/uv/install.sh | sh
# então recarregue o shell: source ~/.bashrc ou equivalente
```

Entre na pasta do projeto:

```
cd rpg-soundboard
```

Sincronize dependências (cria `.venv` e instala tudo conforme uv.lock):
```
uv sync
```

Rode a aplicação:

```
uv run python main.py
```

---

# 🎵 Formatos de áudio suportados

O player aceita os formatos mais comuns:

* mp3
* ogg
* wav
* flac
* aac
* m4a

---

# 🧠 Arquitetura

O projeto segue um princípio simples de **separação de responsabilidades**:

| Camada       | Responsabilidade          |
|--------------|---------------------------|
| GUI          | Interface e interação     |
| SoundManager | Controle de áudio         |
| Widgets      | Componentes reutilizáveis |
| Config       | Persistência              |
| Utils        | Funções auxiliares        |

Isso facilita:

* manutenção
* testes
* adição de novas features.

---

# 🚀 Possíveis melhorias futuras

Algumas ideias para evolução do projeto:

* 🔢 atalhos numéricos para efeitos rápidos
* ⭐ sistema de **favoritos**
* 🎭 perfis de campanha
* 📂 playlists de trilhas
* 🔎 busca nas listas
* 🎚 mixer global
* 🎛 fade in / fade out de trilhas
* 🎲 integração com sistemas de RPG virtual.

---

# 🐛 Problemas conhecidos

* Requer **VLC instalado no sistema**.
* Algumas distribuições Linux precisam do pacote `vlc` ou `libvlc` manualmente.

---

# 📜 Licença

Projeto distribuído sob licença **MIT**.

Você pode:

* usar
* modificar
* distribuir

livremente.

---

# ❤️ Motivação

Este projeto foi criado para facilitar a vida de **mestres de RPG** que querem usar trilhas e efeitos sonoros **sem depender de aplicativos pesados ou cheios de distrações durante a sessão**.

O objetivo é manter:

* **velocidade**
* **simplicidade**
* **controle imediato**
* **confiabilidade durante sessões ao vivo**.

---

Se você quiser contribuir ou sugerir melhorias, abra uma **issue ou pull request**.
