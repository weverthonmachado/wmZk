import sublime, sublime_plugin
import re
import os
import csv
import time
import sys
import subprocess
import shlex

if os.path.dirname(__file__) not in sys.path:
    sys.path.append(os.path.dirname(__file__))
import biblib.bib
import biblib.algo
import pypandoc
import urllib
import tempfile
import wmZk_index


# Settings
def plugin_loaded():
    global NOTES_FOLDER
    global INDEX_FOLDER
    global SYNTAX
    global ATTACHMENTS
    global REFERENCES_LIST
    global LIBRARY
    global BIB_FILE
    global CSL
    global R_PATH
    global PYTHON_PATH
    global RIPGREP_PATH

    settings = sublime.load_settings("wmZk.sublime-settings")
    NOTES_FOLDER = settings.get("notes_folder")
    INDEX_FOLDER = os.path.join(sublime.packages_path(), "wmZk/index")
    SYNTAX =  settings.get("notes_syntax") 
    ATTACHMENTS =  settings.get("attachments_folder")
    BIB_FILE = settings.get("bib_file") 
    CSL = settings.get("csl") 
    R_PATH = settings.get("r_path")
    PYTHON_PATH = settings.get("python_path")
    RIPGREP_PATH = settings.get("ripgrep_path")

    if BIB_FILE:
        bib_object = open(BIB_FILE, "r", encoding="utf-8")
        LIBRARY = dict(list(biblib.bib.Parser().parse(bib_object).get_entries().items()))
        REFERENCES_LIST = []
        for key in LIBRARY:
            record = LIBRARY[key]
            if "author" in record:
                author = biblib.algo.tex_to_unicode(record["author"])
                n_authors = len(author.split("and"))
                if n_authors > 3:
                    author = author.split("and")[0] + "et al"
            elif "editor" in record:
                author = record["editor"]
            if "year" in record:
                year = record["year"]
            else:
                year = "s.d."
            title = re.sub(r'{\\textless}/*i{\\textgreater}|{\\text.*?}', '', record["title"])
            title = biblib.algo.tex_to_unicode(title)
            row = "%s - %s (%s) %s" % (record.key, author, year, title)
            REFERENCES_LIST.append(row)
            REFERENCES_LIST.sort()


LINKING_NOTE_VIEW = None
RESULT_VIEW = None

#### Basic functions
###

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
    with open(
            os.path.join(folder, ".index.zkdata"), encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile)
        index = list(reader)
    tag_list = []
    for row in index:
        note_tags = row['tags']
        for tag in note_tags.split(";"):
            if tag not in tag_list and tag != "":
                tag_list.append(tag)
    tag_list.sort()
    return tag_list


def get_notes_by_tag(folder, tag):
    '''
    Retorna lista de notas que contém a tag fornecida
    '''
    with open(
            os.path.join(folder, ".index.zkdata"), encoding="utf8") as csvfile:
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
    with open(
            os.path.join(folder, ".links.zkdata"), encoding="utf8") as csvfile:
        reader = csv.reader(csvfile)
        index = list(reader)
    filtered = list(filter(lambda row: id in row[1], index))
    note_list = []
    for row in filtered:
        note_list.append(row[0] + " " + row[2])
    return note_list


def get_note_title_by_id(folder, id):
    '''
    Retorna titulo de nota com o id fornecido
    '''
    with open(
            os.path.join(folder, ".index.zkdata"), encoding="utf8") as csvfile:
        reader = csv.DictReader(csvfile)
        index = list(reader)
    note_title = None
    for row in index:
        if row["id"] == id:
            note_title = row["title"]
    return note_title

def get_citation(ref):
    '''
    Retorna info bibliográfica básica para a citekey fornecida
    '''
    entry = LIBRARY[ref.lower()]
    # Função para substituir por et al se mais de 3 autores
    def get_author(entry):
        author = entry["author"]
        n_authors = len(author.split("and"))
        if n_authors > 3:
            author = author.split("and")[0] + "et al"
        return author

    if "year" in entry:
        year = entry["year"]
    else:
        year = "s.d."

    if "file" in entry:
        file = entry["file"].replace(":C$\\backslash$", "C")
        file = file.replace(":pdf", "")
        file = '<br><a href="file://%s">%s</a>' % (file, "🗎 Open")
    else:
        file = ""

    if entry.typ == "article":       
        reference = "%s. (%s) %s. <em>%s</em> %s" % (get_author(entry), year, entry["title"], entry["journal"], file)
    
    if entry.typ in ["book", "phdthesis"]:
        if "author" in entry:
            author = get_author(entry)
        elif "editor" in entry:
            author = entry["editor"] + " (Ed.)"
        else:
            author = "no author"

        reference = "%s. (%s) <em>%s</em> %s" % (author, year, entry["title"], file)

    if entry.typ == "incollection":
        reference = "%s. (%s) %s. In: %s. <em>%s</em> %s" % (get_author(entry), year, entry["title"], entry["editor"], entry["booktitle"], file)

    reference = biblib.algo.tex_to_unicode(reference)
    return reference

def update_data(links=False):
    '''
    Checa se indíce (ou lista de links) foi atualizado nos últimos 5 minutos.
    Se não, atualiza. 
    links = True atualiza lista de links em vez de notas.
    '''
    if links:
        timestamp_file = ".links.zktimestamp"
    else:
        timestamp_file = ".index.zktimestamp"
    # Última atualização
    timestamp = open(os.path.join(INDEX_FOLDER, timestamp_file), "r").read()
    timestamp = float(timestamp)
    # É antes de 5 minutos atrás?
    if timestamp < (time.time() - 300):
        if links:
            wmZk_index.update_links(NOTES_FOLDER, INDEX_FOLDER, False)
        else:
            wmZk_index.update_index(NOTES_FOLDER, INDEX_FOLDER, False)



###
# Sublime commands
###

class WmzkOpenNoteCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        update_data(links=False)
        global note_list
        note_list = get_note_list(INDEX_FOLDER)
        self.view.window().show_quick_panel(note_list, self.on_done)

    def on_done(self, selection):
        if selection == -1:
            return
        id = note_list[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(NOTES_FOLDER, basename)
        self.view.window().open_file(filename)


class WmzkInsertLinkCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        update_data(links=False)
        global note_list
        note_list = get_note_list(INDEX_FOLDER)
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
                sublime.message_dialog(
                    '-- Save the current note before creating a new one. --')
                return
            current_id = os.path.basename(current_note)
            current_id = current_id.replace(".md", "")
            link = "[[" + new_id + "]]"
            self.view.run_command("insert", {"characters": link})
            contents = '---\nid: ' + new_id + '\ntitle: $1\ntags: #rascunho\n---\n\n$2\n\n---\n## Contexto\n- Origem: [[' + current_id + ']]'
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
        tag_list = get_tag_list(INDEX_FOLDER)
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
            sublime.message_dialog('-- Save the note before inserting an image --')
            return
        note_id = os.path.basename(current_note)
        note_id = note_id.replace(".md", "")
        img_basename = note_id + "_img"
        attachment_list = os.listdir(os.path.join(NOTES_FOLDER, ATTACHMENTS))
        # Numera anexos (se é o primeiro, sufixo é _img1, e assim em diante)
        counter = len(re.findall(img_basename, ", ".join(attachment_list)))
        img_name = img_basename + str(counter+1) + ".png"
        pkg_path = sublime.packages_path()
        helper_path = os.path.join(pkg_path, "wmZk/img_clipboard.py")
        img_path = os.path.join(NOTES_FOLDER, ATTACHMENTS, img_name)
        if PYTHON_PATH:
            pythonexe = '"' + PYTHON_PATH + '" '
        else:
            pythonexe = "python"
        command = pythonexe + ' "' + helper_path + '" "' + img_path + '" '
        subprocess.check_output(command, shell=True)
        link = "![](" + ATTACHMENTS + img_name + ")"
        self.view.run_command("insert", {"characters": link})


class WmzkNotesFromTag(sublime_plugin.TextCommand):
    def run(self, edit):
        update_data(links=False)
        global tag_list
        tag_list = get_tag_list(INDEX_FOLDER)
        self.view.window().show_quick_panel(tag_list, self.on_done_tag)

    def on_done_tag(self, selection):
        global note_list
        if selection == -1:
            return
        tag = tag_list[selection]
        note_list = get_notes_by_tag(INDEX_FOLDER, tag)
        note_list = ["..."] + note_list
        self.view.window().show_quick_panel(note_list, self.on_done_note)

    def on_done_note(self, selection):
        if selection == -1:
            return
        if selection == 0:
            self.view.window().run_command('wmzk_notes_from_tag')
            return
        id = note_list[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(NOTES_FOLDER, basename)
        self.view.window().open_file(filename)


class ResultView(sublime_plugin.EventListener):
    '''
    Helper para BrowseResults.
    Checa se o view com a nota da lista de resultados já carregou.
    '''
    def on_load(self, view):
        global RESULT_VIEW
        global FOCUS_ON_MATCH
        if view == RESULT_VIEW:
            for region in view.find_all(REGEXID, sublime.IGNORECASE):
                view.sel().add(region)
            if FOCUS_ON_MATCH:
                # Como show_at_center nao está funcionando bem aqui,
                # foca em ponto anterior aoinício da região
                # para que link fique mais ou menos no meio
                view.show_at_center(view.find_all(REGEXID, sublime.IGNORECASE)[0].begin()-250)
                FOCUS_ON_MATCH = False
            RESULT_VIEW = None


class QuickPanelFocus(sublime_plugin.EventListener):
    '''
    Helper para BrowseResults.
    Checa se quick panel está em foco.
    '''

    def on_activated(self, view):
        """
        This method is called whenever a view (tab, quick panel, etc.) gains
        focus, but we only want to get the quick panel view, so we use a flag
        Fonte: https://stackoverflow.com/a/30627601
        """
        if hasattr(
                sublime,
                'capturingQuickPanelView') and sublime.capturingQuickPanelView:
            sublime.capturingQuickPanelView = False
            """View saved as an attribute of the global variable sublime so
            it can be accessed from your plugin or anywhere"""
            sublime.quickPanelView = view


class WmzkLinkingNotes(sublime_plugin.TextCommand):
    '''
    Mostra notas que linkam para a nota atual  +
    Highlight ocorrencias
    '''
    def run(self, edit):
        current_note = self.view.file_name()
        if current_note is None:
            sublime.message_dialog(
                '-- Note must be saved to find linking notes. --')
            return
        update_data(links=True)
        note_id = os.path.basename(current_note)
        note_id = note_id.replace(".md", "")
        regex = "\[\[\s*" + note_id + "\s*\]\]|@" + note_id
        linking_notes = get_notes_by_link(INDEX_FOLDER, note_id)
        if len(linking_notes) == 0:
            sublime.message_dialog('-- Found no links to the current note --')
            return
        header = str(len(linking_notes)) + " notes linking to " + note_id
        self.view.run_command(
            'wmzk_browse_results', {'results': linking_notes, 'header': header, 'regex': regex })


class HoverLink(sublime_plugin.EventListener):
    '''
    Exibe titulo (clicável) da nota ao parar sobre link
    '''

    def on_hover(self, view, point, zone):
        if zone == sublime.HOVER_TEXT:
            scope = view.scope_name(point)
            if  any(item in scope for item in ["meta.link.wiki.markdown", "meta.citekey.markdown", "meta.link.reference.literal.markdown"]):
                global my_view
                global note_title
                my_view = view
                region = view.word(point)
                # Caso seja meta.link.reference... (ou seja, dentro de colchetes), checa
                # se é precedido por @ antes de continuar
                if "meta.link.reference.literal.markdown" in scope:
                    preceding = view.substr(sublime.Region(region.begin()-1, region.begin()))
                    if preceding is not "@":
                        return
                note_id = view.substr(region)
                note_title = get_note_title_by_id(INDEX_FOLDER, note_id)
                if note_title is None:
                    content = get_citation(note_id)
                else:
                    content = """
                             <a href="%s">%s</a><br><a href="%s">%s</a>
                              """ % (note_id, note_title, "copy", "📋")
                html = """
                            <body>
                                <style>
                                    p {
                                        margin-top: 0;

                                    }
                                    a {
                                        text-decoration: none;
                                    }
                                </style>
                                <div>
                                <p>%s</p>
                                </div>
                            </body>
                        """ % (content)
                view.show_popup(
                    html,
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    on_navigate=self.nav)
            elif "markup.underline.link.image.markdown" in scope:
                region = view.extract_scope(point)
                link = os.path.join(NOTES_FOLDER, view.substr(region))
                html = """
                            <body id=show-scope>
                                <style>
                                    a {
                                        text-decoration: none;
                                    }
                                </style>
                                <img src="file://%s">
                            </body>
                        """ % link
                view.show_popup(html, 
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    max_width=600,
                    max_height=600)
            elif "meta.environment.math.latex" in scope:
                all_math = view.find_all("\\${1,2}(.*?)\\${1,2}")
                i = -1
                for r in all_math:
                    i += 1
                    if r.begin() <= point <= r.end():
                        break
                region = all_math[i]
                formula = view.substr(region).replace("$", "")
                formula = urllib.parse.quote(formula)
                url = "http://chart.googleapis.com/chart?cht=tx&chs=35&chl=" + formula
                img = tempfile.NamedTemporaryFile(delete=False)
                img.write(urllib.request.urlopen(url).read())
                img.close()
                urllib.request.urlretrieve(url)
                html = """
                            <body id=show-scope>
                                <style>
                                    a {
                                        text-decoration: none;
                                    }
                                </style>
                                <img src="file://%s">
                            </body>
                        """ % img.name
                view.show_popup(html, 
                    flags=sublime.HIDE_ON_MOUSE_MOVE_AWAY,
                    location=point,
                    max_width=600,
                    max_height=600)

    def nav(self, id):
        if id == "copy":
            sublime.set_clipboard(note_title.strip())
        elif id.startswith("file"):
            os.startfile(id.replace("file://", ""))
        else:
            basename = id + ".md"
            filename = os.path.join(NOTES_FOLDER, basename)
            my_view.window().open_file(filename)


class WmzkCustomSearchCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.window().show_input_panel("Search", "", self.find, None, None)

    def find(self, string):
        update_data(links=False)
        terms_list = shlex.split(string)
        regex = "|".join(terms_list)
        terms = []
        for t in terms_list:
            terms.append("(?=.*?" + t + ")")
        terms = "".join(terms)
        search_string = '"(?s)^' + terms + '"'
        if RIPGREP_PATH:
            ripgrepexe = '"' + RIPGREP_PATH + '"'
        else:
            ripgrepexe = "rg"
        command = ripgrepexe + r' -l -S --pcre2 --type md ' + search_string + r' ' + NOTES_FOLDER
        output = subprocess.check_output(command, shell=True)
        file_list = output.decode("UTF-8").split("\n")
        note_list = []
        for file in file_list:
            note_id = os.path.basename(file)
            note_id = note_id.replace(".md", "")
            # Abaixo a função get_note_title_by_id() copiada
            # já que chamá-la diretamente não funcionou
            with open(
                    os.path.join(INDEX_FOLDER, ".index.zkdata"), encoding="utf8") as csvfile:
                reader = csv.DictReader(csvfile)
                index = list(reader)
            for row in index:
                if row["id"] == note_id:
                    note_title = row["title"]
                    note_list.append(note_id + " " + note_title)
        header = str(len(note_list)) + " notes found"
        self.view.run_command(
            'wmzk_browse_results', {'results': note_list, 'header': header, 'regex': regex })


class WmzkBrowseResultsCommand(sublime_plugin.TextCommand):
    '''
    Esta função é para ser chamada internamente pelo plugin, mais espcificamente pelos comandos
    LinkingNotes e CustomSearch. Ela recebe uma lista de notas (resultado da custom search ou
    de links para notas atuais), um texto (header) para aparecer como primeiro resultado (ex:
    "X notes linking to") e uma regex para dar highlighted. Esta função então produz um painel de
    resultados navegáveis, cujas notas e matches aparecem à medida em que são selecionados no painel
    '''
    def run(self, edit, results, header, regex):
        global results_list
        global REGEXID
        results_list = ["## " + header + " ##"]
        for r in results:
            results_list.append(r)
        REGEXID = regex
        sublime.capturingQuickPanelView = True
        self.view.window().show_quick_panel(results_list, self.on_done, 
                                            sublime.KEEP_OPEN_ON_FOCUS_LOST, 0,
                                            self.on_highlighted)
        self.view.window().run_command(
            'set_layout', {
                'cols': [0.0, 1.0],
                'rows': [0.0, 0.5, 1.0],
                'cells': [[0, 0, 1, 1], [0, 1, 1, 2]]
            }) 

    def on_done(self, selection):
        global RESULT_VIEW
        global FOCUS_ON_MATCH
        self.view.window().run_command('set_layout', {
            'cols': [0.0, 1.0],
            'rows': [0.0, 1.0],
            'cells': [[0, 0, 1, 1]]
        })
        if selection < 1:
            self.view.window().focus_view(self.view)
            return
        id = results_list[selection].split()[0]
        basename = id + ".md"
        filename = os.path.join(NOTES_FOLDER, basename)
        self.view.window().focus_group(0)
        new_view = self.view.window().open_file(filename)
        if not new_view.is_loading():
            for region in new_view.find_all(REGEXID):
                new_view.sel().add(region)
        else:
            RESULT_VIEW = new_view
            FOCUS_ON_MATCH = True

    def on_highlighted(self, selection):
        global RESULT_VIEW
        global FOCUS_ON_MATCH
        if selection == -1:
            return
        if selection > 0:
            id = results_list[selection].split()[0]
            basename = id + ".md"
            filename = os.path.join(NOTES_FOLDER, basename)
            self.view.window().focus_group(1)
            new_view = self.view.window().open_file(filename,
                                                    flags=sublime.TRANSIENT)
            if not new_view.is_loading():
                self.view.window().set_view_index(new_view, 1, 0)
                for region in new_view.find_all(REGEXID, sublime.IGNORECASE):
                    new_view.sel().add(region)
                    # Foca na primeira ocorrência (do link ou termo pesquisado)
                    new_view.show_at_center(new_view.find_all(REGEXID, sublime.IGNORECASE)[0])
            else:
                RESULT_VIEW = new_view
                FOCUS_ON_MATCH = True
        sublime.set_timeout(self.restoreQuickPanelFocus, 100)

    def restoreQuickPanelFocus(self):
        self.view.window().focus_view(sublime.quickPanelView)


class WmzkNewBiblioNote(sublime_plugin.TextCommand):
    def run(self, edit):
        self.view.window().show_quick_panel(REFERENCES_LIST, self._paste)

    def is_enabled(self):
        return True

    def _paste(self, item):
        global new_view
        global id
        if item == -1:
            id = "Novo fichamento"
            title = ""
            complete = "Referência completa aqui"
        else:
            result = REFERENCES_LIST[item]
            id = result.split(' ')[0]
            title = result.split(') ')[1]
            title = re.sub("{|}", "", title)
            ref = "@" + id
            text = '---\nnocite: \"' + ref + '\"\n---'
            arg_bib = "--bibliography=" + BIB_FILE
            args = ["--columns=500",
                    "--filter=pandoc-citeproc",
                    arg_bib]            
            if CSL:
                arg_csl = "--csl=" + CSL
                args.append(arg_csl)  
            complete = pypandoc.convert_text(text, 'plain', format='markdown+yaml_metadata_block', extra_args=args)
        contents = ('---\nid: %s\ntitle: "%s"\ntags: #fichamentos\n---\n\n%s$1\n\n'
                    "Resumo:\n>\n\n# Comentários gerais\n\n$2\n\n# Objetivos e questões de pesquisa\n\n\n"
                    "# Metodologia\n\n\n# Principais resultados e contribuições\n\n\n"
                    "# Como influencia minha pesquisa?")  % (id, title, complete)
        new_view = self.view.window().new_file()
        new_view.set_syntax_file(SYNTAX)
        new_view.run_command("insert_snippet", {"contents": contents})
        sublime.set_timeout(self.setname, 100)

    def setname(self):
        new_view.set_name(id)


class WmzkSidebar(sublime_plugin.TextCommand):
    '''
    Mostra notas que linkam para a nota atual  +
    Highlight ocorrencias
    '''
    def run(self, edit):
        current_view = self.view
        current_note = self.view.file_name()
        if current_note is None:
            sublime.message_dialog(
                '-- Note must be saved to find linking notes. --')
            return
        note_id = os.path.basename(current_note)
        note_id = note_id.replace(".md", "")
        linking_notes = get_notes_by_link(INDEX_FOLDER, note_id)
        if len(linking_notes) == 0:
            content = "Found no links to the current note"
        else:
            # Captura ids da lista
            linking_notes = [i.split()[0] for i in linking_notes]
            # Transforma ids em links
            linking_notes =[re.sub(r'([^\d].*)', r'@\1', id) for id in linking_notes]
            linking_notes =[re.sub(r'(\d{12})', r'[[\1]]', id) for id in linking_notes]
            content = linking_notes
        self.view.window().run_command(
            'set_layout', 
            {'cols': [0.0, 0.8, 1.0],
            'rows': [0.0, 1.0],
            'cells': [[0, 0, 1, 1], [1, 0, 2, 1]]
        })
        self.view.window().focus_group(1)
        print("\n".join(content))


class WmzkNotesNetwork(sublime_plugin.TextCommand):
    def run(self, edit):
        update_data(links=False)
        update_data(links=True)
        global NETWORK_PROCESS
        pkg_path = sublime.packages_path()
        vis_path = os.path.join(pkg_path, "wmZk/visualiza_notas_shinyApp.R")
        if R_PATH:
            rscriptexe = '"' + R_PATH + '"'
        else:
            rscriptexe = "Rscript.exe"
        command = rscriptexe + ' "' + vis_path + '" ' + INDEX_FOLDER + ' ' + NOTES_FOLDER
        NETWORK_PROCESS = subprocess.Popen(command, shell=False)
        NETWORK_PROCESS


# Funções de atualização para menu
class WmzkMenuUpdateIndex(sublime_plugin.TextCommand):
    def run(self, edit):
        wmZk_index.update_index(NOTES_FOLDER, INDEX_FOLDER, False)

class WmzkMenuRecreateIndex(sublime_plugin.TextCommand):
    def run(self, edit):
        wmZk_index.update_index(NOTES_FOLDER, INDEX_FOLDER, True)

class WmzkMenuUpdateLinks(sublime_plugin.TextCommand):
    def run(self, edit):
        wmZk_index.update_links(NOTES_FOLDER, INDEX_FOLDER, False)

class WmzkMenuRecreateLinks(sublime_plugin.TextCommand):
    def run(self, edit):
        wmZk_index.update_links(NOTES_FOLDER, INDEX_FOLDER, True)