
import sublime, sublime_plugin
import re
import os
import csv
import time
# Importa plugin wm_citer para fichamento
from Citer import citer
import subprocess


# Globals. Depois posso obter os valores de um arquivo
# de configuração
FOLDER = "C:/Dropbox/notas"
SYNTAX = "Packages/User/Markdown.sublime-syntax"
ATTACHMENTS = "anexos/"
LINKING_NOTE_VIEW = None

def get_note_list(folder):
    with open(os.path.join(folder, ".index.zkdata"),
              encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile)
        index = list(reader)
    note_list = []
    for row in index:
        note_list.append(row["id"] + " " + row["title"])
    return note_list

def get_tag_list(folder):
    with open(os.path.join(folder, ".index.zkdata"),
          encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile)
        index = list(reader)
    tag_list = []
    for row in index:
        note_tags = row['tags']
        for tag in note_tags.split(";"):
            if tag not in tag_list and tag!="":
                tag_list.append(tag)
    tag_list.sort()
    return tag_list

def get_notes_by_tag(folder, tag):
    '''
    Retorna lista de notas que contém a tag fornecida
    '''
    with open(os.path.join(folder, ".index.zkdata"),
          encoding="utf8") as csvfile:
        reader = csv.reader(csvfile)
        index = list(reader)
    filtered = list(filter(lambda row: tag in row[2], index))
    note_list = []
    for row in filtered:
        note_list.append(row[0] + " " + row[1])
    return note_list


def get_notes_by_link(folder, id):
    '''
    Retorna lista de notas que linkam para o id fornecido
    '''
    with open(os.path.join(folder, ".links.zkdata"),
          encoding="utf8") as csvfile:
        reader = csv.reader(csvfile)
        index = list(reader)
    filtered = list(filter(lambda row: id in row[1], index))
    n = len(filtered)
    note_list = ["-- " + str(n) + " notes linking to " + id + " --"]
    for row in filtered:
        note_list.append(row[0] + " " + row[2])
    return note_list

def get_note_title_by_id(folder, id):
    '''
    Retorna titulo de nota com o id fornecido
    '''
    with open(os.path.join(folder, ".index.zkdata"),
              encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile)
        index = list(reader)
    for row in index:
        if row["id"]==id:
            note_title = row["title"]
    return note_title

class WmzkOpenNoteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global note_list
        note_list = get_note_list(FOLDER)
        self.view.window().show_quick_panel(note_list, self.on_done)

    def on_done(self, selection):
        if selection == -1:
            return
        id = note_list[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(FOLDER, basename)
        new_view = self.view.window().open_file(filename)

class WmzkInsertLinkCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global note_list
        note_list = get_note_list(FOLDER)
        note_list = ["-- Create new note --"] + note_list
        self.view.window().show_quick_panel(note_list, self.on_done)

    def on_done(self, selection):
        if selection == -1:
            self.view.run_command("insert", {"characters": "[["})
            return
        if selection == 0:
            new_id = time.strftime("%Y%m%d%H%M")
            current_note = self.view.file_name()
            if current_note is None:
                sublime.status_message('-- Save the current note before creating a new one. --')
                return
            current_id = os.path.basename(current_note)
            current_id = current_id.replace(".md", "")
            link = "[[" + new_id + "]]"
            self.view.run_command("insert", {"characters": link})
            contents = '---\nid: ' + new_id + '\ntitle: $1\ntags: ["#rascunho"]\n---\n\n$2\n\n---\n## Contexto\n- Origem: [[' + current_id + ']]'
            new_view = self.view.window().new_file()
            new_view.set_syntax_file(SYNTAX)
            new_view.set_name(new_id)
            new_view.run_command("insert_snippet", {"contents": contents})
        else:
            id = note_list[selection].split()[0]
            link = "[[" + id + "]]"
            self.view.run_command("insert", {"characters": link})

class WmzkInsertTagCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        global tag_list
        tag_list = get_tag_list(FOLDER)
        self.view.window().show_quick_panel(tag_list, self.on_done)

    def on_done(self, selection):
        if selection == -1:
            self.view.run_command("insert", {"characters": "#"})
            return
        tag = tag_list[selection]
        self.view.run_command("insert", {"characters": tag})

class WmzkNewNoteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        id = time.strftime("%Y%m%d%H%M")
        contents = "---\nid: " + id + "\ntitle: $1\ntags: \n---\n\n$2\n\n---\n## Contexto\n"
        new_view = self.view.window().new_file()
        new_view.set_syntax_file(SYNTAX)
        new_view.set_name(id)
        new_view.run_command("insert_snippet", {"contents": contents})



class WmzkNewBiblioNoteCommand(sublime_plugin.TextCommand):

    """
    Esta função depende de comandos do pacote Citer. Um nova modificação
    a partir de wm_citer.py
    """
    current_results_list = []

    def run(self, edit):
        citer.refresh_settings()
        ctk = citer.citekeys_menu()
        if len(ctk) > 0:
            self.current_results_list = ctk
            self.view.window().show_quick_panel(self.current_results_list,
                                                self._paste)

    def is_enabled(self):
        """Determines if the command is enabled
        """
        return True

    def _paste(self, item):
        """Paste item into buffer
        """
        if item == -1:
            id = "Novo fichamento"
            contents = "---\nid: $1\ntitle: $2\ntags: ['#fichamento']\n---\n\nreferência completa aqui\n\nResumo:\n\n>\n\n# Comentários gerais\n\n\n# Objetivos e questões de pesquisa\n\n\n# Metodologia\n\n\n# Principais resultados e contribuições\n\n\n# Como influencia minha pesquisa?"
        else:
            result = self.current_results_list[item][0]
            citekey = result.split(' ')[0]
            id = citekey
            title = result.split(') ')[1]
            title = re.sub("{|}", "", title)
            ref = "@" + citekey
            # Converte citekey em citacao completa com pandoc
            textfile = open("C:\\Users\\WEVERT~1\\AppData\\Local\\Temp\\textfile.md", "w")
            textfile.write('---\nnocite: \"' + ref +'\"\n...')
            textfile.close()
            command = 'pandoc -f markdown+yaml_metadata_block --columns=500 --filter=pandoc-citeproc --bibliography=C:/Dropbox/recursos/library.bib --csl=C:/Dropbox/recursos/pandoc/csl/APA-etal.csl -t plain C:\\Users\\WEVERT~1\\AppData\\Local\\Temp\\textfile.md'
            complete = subprocess.check_output(command, shell=True).decode("utf-8")
            contents = "---\nid: " + citekey + "\ntitle: " + title + "\ntags: ['#fichamento']\n---\n\n" + complete + "$1\n\nResumo:\n\n>\n\n# Comentários gerais\n\n$2\n# Objetivos e questões de pesquisa\n\n\n# Metodologia\n\n\n# Principais resultados e contribuições\n\n\n# Como influencia minha pesquisa?"
        new_view = self.view.window().new_file()
        new_view.set_syntax_file(SYNTAX)
        new_view.set_name(id)
        new_view.run_command("insert_snippet", {"contents": contents})

class WmzkInsertImageClipboardCommand(sublime_plugin.TextCommand):
    '''
    Essa é uma gambiarra para colar uma imagem do clipboard.
    Salva automaticamente imagem na pasta anexos do diretório
    de notas, com o nome {id da nota}_img1.png e insere link
    no texto.``
    '''
    def run(self, edit):
        current_note = self.view.file_name()
        if current_note is None:
            sublime.status_message('-- Save the note before inserting an image --')
            return
        note_id = os.path.basename(current_note)
        note_id = note_id.replace(".md", "")
        img_basename = note_id + "_img"
        attachment_list = os.listdir(os.path.join(FOLDER, ATTACHMENTS))
        # Numera anexos (se é o primeiro, sufixo é _img1, e assim em diante)
        counter = len(re.findall(img_basename, ", ".join(attachment_list)))
        img_name = img_basename + str(counter+1) + ".png"
        pkg_path = sublime.packages_path()
        helper_path = os.path.join(pkg_path, "wmZk/img_clipboard.py")
        img_path = os.path.join(FOLDER, ATTACHMENTS, img_name)
        command =  'C:/Python36/python.exe "' + helper_path + '" ' + img_path
        p = subprocess.check_output(command, shell=True)
        link = "![](" + ATTACHMENTS + img_name + ")"
        self.view.run_command("insert", {"characters": link})


class WmzkNotesFromTag(sublime_plugin.TextCommand):
    def run(self, edit):
        global tag_list
        tag_list = get_tag_list(FOLDER)
        self.view.window().show_quick_panel(tag_list, self.on_done_tag)

    def on_done_tag(self, selection):
        global note_list
        if selection == -1:
            return
        tag = tag_list[selection]
        note_list = get_notes_by_tag(FOLDER, tag)
        note_list =  ["..."] + note_list
        self.view.window().show_quick_panel(note_list, self.on_done_note)

    def on_done_note(self, selection):
        if selection == -1:
            return
        if selection == 0:
            self.view.window().run_command('wmzk_notes_from_tag')
            return
        id = note_list[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(FOLDER, basename)
        new_view = self.view.window().open_file(filename)

class WmzkLinkingNotes(sublime_plugin.TextCommand):
    '''
    Mostra notas que linkam para a nota atual
    '''
    def run(self, edit):
        global linking_notes
        current_note = self.view.file_name()
        if current_note is None:
            sublime.status_message('-- Note must be saved to find linking notes. --')
            return
        note_id = os.path.basename(current_note)
        note_id = note_id.replace(".md", "")
        linking_notes = get_notes_by_link(FOLDER, note_id)
        if len(linking_notes) == 0:
            sublime.status_message('-- Found no links to the current note --')
        self.view.window().show_quick_panel(linking_notes, self.on_done)

    def on_done(self, selection):
        if selection < 1:
            return
        id = linking_notes[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(FOLDER, basename)
        new_view = self.view.window().open_file(filename)



class LinkingNote(sublime_plugin.EventListener):
    '''
    Checa se linking note já carregou
    '''
    def on_load(self, view):
        global LINKING_NOTE_VIEW
        global FOCUS_ON_LINK
        if view == LINKING_NOTE_VIEW:
            for region in view.find_all(REGEXID):
                view.sel().add(region)
            if FOCUS_ON_LINK:
                # Como show_at_center nao está funcionando bem aqui,
                # foca em ponto anterior aoinício da região
                # para que link fique mais ou menos no meio
                view.show_at_center(view.find_all(REGEXID)[0].begin()-250)
                FOCUS_ON_LINK = False
            LINKING_NOTE_VIEW = None

class QuickPanelFocus(sublime_plugin.EventListener):
    '''
    Checa se quick panel está em foco
    '''
    def on_activated(self, view):
        """This method is called whenever a view (tab, quick panel, etc.) gains focus, but we only want to get the quick panel view, so we use a flag"""
        if hasattr(sublime, 'capturingQuickPanelView') and sublime.capturingQuickPanelView == True:
            sublime.capturingQuickPanelView = False
            """View saved as an attribute of the global variable sublime so it can be accesed from your plugin or anywhere"""
            sublime.quickPanelView = view


class WmzkLinkingNotesExtra(sublime_plugin.TextCommand):
    '''
    Mostra notas que linkam para a nota atual  +
    Highlight ocorrencias
    '''

    def restoreQuickPanelFocus(self):
        """Restore focus to quick panel is as easy as focus in the quick panel view, that the eventListener has previously captured and saved"""
        self.view.window().focus_view(sublime.quickPanelView)

    def run(self, edit):
        global linking_notes
        global note_id
        global REGEXID
        current_note = self.view.file_name()
        if current_note is None:
            sublime.status_message('-- Note must be saved to find linking notes. --')
            return
        note_id = os.path.basename(current_note)
        note_id = note_id.replace(".md", "")
        linking_notes = get_notes_by_link(FOLDER, note_id)
        if len(linking_notes) == 0:
            sublime.status_message('-- Found no links to the current note --')
            return
        sublime.capturingQuickPanelView = True
        self.view.window().show_quick_panel(linking_notes, self.on_done, sublime.KEEP_OPEN_ON_FOCUS_LOST, 0, self.on_highlighted)
        self.view.window().run_command('set_layout', {
            'cols': [0.0, 1.0],
            'rows': [0.0, 0.5, 1.0],
            'cells': [[0, 0, 1, 1], [0, 1, 1,2]]
        })
        REGEXID = "\[\[\s*" + note_id + "\s*\]\]|@" + note_id


    def on_done(self, selection):
        global LINKING_NOTE_VIEW
        global FOCUS_ON_LINK
        self.view.window().run_command('set_layout', {
            'cols': [0.0,1.0],
            'rows': [0.0, 1.0],
            'cells': [[0, 0, 1, 1]]
        })
        if selection < 1:
            self.view.window().focus_view(self.view)
            return
        id = linking_notes[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(FOLDER, basename)
        self.view.window().focus_group(0)
        new_view = self.view.window().open_file(filename)
        if not new_view.is_loading():
            for region in new_view.find_all(REGEXID):
                new_view.sel().add(region)
        else:
            LINKING_NOTE_VIEW = new_view
            FOCUS_ON_LINK = False

    def on_highlighted(self, selection):
        global LINKING_NOTE_VIEW
        global FOCUS_ON_LINK
        if selection == -1:
            return
        id = linking_notes[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(FOLDER, basename)
        self.view.window().focus_group(1)
        new_view = self.view.window().open_file(filename, flags=sublime.TRANSIENT)
        if not new_view.is_loading():
            self.view.window().set_view_index(new_view, 1, 0)
            for region in new_view.find_all(REGEXID):
                new_view.sel().add(region)
                # Foca na primeia ocorrência do link
                new_view.show_at_center(new_view.find_all(REGEXID)[0])
        else:
            LINKING_NOTE_VIEW = new_view
            FOCUS_ON_LINK = True
        sublime.set_timeout(self.restoreQuickPanelFocus, 100)



class HoverLink(sublime_plugin.EventListener):
    '''
    Exibe titulo (clicável) da nota ao parar sobre link
    '''
    def on_hover(self, view, point, zone):
        if zone == sublime.HOVER_TEXT:
            scope = view.scope_name(point)
            if "markup.zettel.link" in scope:
                global my_view
                global note_title
                my_view = view
                region = view.word(point)
                note_id = view.substr(region)
                note_title = get_note_title_by_id(FOLDER, note_id)

                html = """
                            <body id=show-scope>
                                <style>
                                    a {
                                        text-decoration: none;
                                    }
                                </style>
                                <a href="%s">%s</a>
                                <a href="%s">%s</a>
                            </body>
                        """ % (note_id, note_title, "copy", "📋")
                view.show_popup(html, flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY, location=point, on_navigate=self.nav)

    def nav(self, id):
        if id == "copy":
            clip = subprocess.Popen(['clip'], stdin=subprocess.PIPE)
            clip.communicate(input=note_title.strip().encode('utf-16'))
        else:
            basename = id + ".md"
            filename = os.path.join(FOLDER, basename)
            my_view.window().open_file(filename)