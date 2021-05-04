'''
wmZk

Funções para manter índice de notas em plain text, a serem usadas pelo
plugin fo Sublime Text.
'''
import os
import re
import sys
import markdown
import time
import csv
from itertools import islice
from operator import itemgetter


# ----------------------------------------------------------
# Funções básicas
# ----------------------------------------------------------

def get_modified_notes(folder, timestamp=0):
    '''
    Retorna lista de arquivos .md em `folder` modificados desde `timestamp`
    (default retorna todos os arquivos)
    '''
    modified = []
    for root, dirs, files in os.walk(folder):
        for basename in files:
            filename = os.path.join(root, basename)
            status = os.stat(filename)
            if basename.endswith(".md") and (status.st_mtime > timestamp):
                modified.append(filename)
    return modified


def get_notes_metadata(filelist, index=None, get_body_tags=False):
    '''
    Loop por `filelist` e cria uma lista de listas com metadados das notas.
    Se uma lista de listas `index` é fornecida, registros são acrescentados ou 
    atualizados.
    Retorna o a lista de listas, número de notas criadas e número de notas atualizadas.
    Layout da lista de listas (variáveis): 
    id, title, tags, modified

    Se get_body_tags = True, lê o conteúdo todo da nota e identifica tags tbm no texto
    (não só no campo de "tags")
    '''
    if index is None:
        index = []
    else:
        #remove header
        del index[0]
        # converte modified para numerico
        for item in index:
            item[3] = float(item[3])
    md = markdown.Markdown(extensions = ["markdown.extensions.meta:MetaExtension"])
    count_new = 0
    count_update = 0
    for file in filelist:
        # Lê as primeiras 8 linhas
        with open(file, encoding="utf8") as myfile:
            header = list(islice(myfile, 8))
        html = md.convert("".join(header))
        id = md.Meta['id'][0]
        title = md.Meta['title'][0].strip('"').strip("'")
        tags = md.Meta['tags'][0]
        tags = re.sub(r"[\[\]\s\'\"]", "", tags).split(",")
        if get_body_tags:
            # Buscar tags tbm no corpo da nota.
            # Lê nota inteira e usa regex
            text = open(file, "r", encoding="utf8").read()
            body_tags = re.findall(r"(#\w+\.?\w+)", text)
            # combina e remove duplicatas
            tags = list(set(tags+body_tags))
        tags = ";".join(tags)
        modified_time = os.stat(file).st_mtime
        # Se id já existe em index, atualiza item;
        # se não, append item
        if any(id in sublist for sublist in index):
            item_updated = [id, title, tags, modified_time]
            index = [item_updated if item[0]==id else item for item in index]
            count_update += 1
        else:
            index.append([id, title, tags, modified_time])
            count_new += 1
    # ordena decrescente com base na coluna modified 
    index = sorted(index, key=itemgetter(3), reverse=True)
    index.insert(0, ["id", "title", "tags", "modified"])
    return index, count_new, count_update


def get_links(filelist, linklist=None):
    '''
    Loop por `filelist` e coleta links para outras notas. Além dos links no 
    formato wiki `[[201901131249]]`, também identifica links com o formato 
    `@citekey` para notas bibliográficas.
    Retorna lista de listas com colunas 'from', 'to', 'fromtitle'. 
    Caso a lista de listas `linklist` seja fornecida, links são acrescentados ou removidos.
    ''' 
    if linklist is None:
        linklist = []
    else:
        #remove header
        del linklist[0]
    for file in filelist:
        text = open(file, "r", encoding="utf8").read()
        id = re.findall(r"id:\s*(\d{12}|[^\s\d]+\d{4}\w*)", text)[0]
        fromtitle =  re.findall(r"\ntitle:\s*(.*)\n", text)[0].strip("'").strip('"')
        # Exclui da linklist os registros anteriores desta nota
        linklist = [item for item in linklist if not item[0]==id]
        found_links = re.findall(r"(?<=\[\[)\s*\d{12}\s*(?=\]\])|(?<=@)[^\s\d]+\d{4}\w*", text)
        if len(found_links) > 0:
            for link in list(set(found_links)):
                # Ignora referências à própria nota (geralmente em notas bibliográficas)
                if link != id:
                    linklist.append([id, link, fromtitle])
    linklist.insert(0, ["from","to", "fromtitle"])
    return linklist

def log(folder, count_new=0, count_update=0, links=False):
    '''
    Registra operação em log file e timestamp
    '''
    now = time.time()
    now_string = time.strftime("%Y-%m-%d %H:%M:%S - ", time.localtime(now))

    if links:
        timestamp = open(os.path.join(folder, ".links.zktimestamp"), "w", encoding="utf8")
        message = now_string + "Links atualizados"
    else:
        timestamp = open(os.path.join(folder, ".index.zktimestamp"), "w", encoding="utf8")
        message = "\n" + now_string + str(count_new) + " notas novas, " + str(count_update) + " notas atualizadas"
        if count_new > 0 or count_update > 0:
            logfile = open(os.path.join(folder, ".zklog.txt"), "a", encoding="utf8")
            logfile.write(message)
            logfile.close()

    timestamp.write(str(now))
    timestamp.close()
    print(message)

def index_android(index, folder):
    '''
    Cria índice para uso do aplicativo Epsilon notes no Android. 
    Recebe lista de notas e salva arquivo markdown
    '''
    # seleciona primeiros 10 elementos, excluindo header
    # (ou seja, notas mais recentes)
    subset = index[1:10]
    # transforma cada elemento em uma string de id e titulo,
    # já com links em sintaxe markdown
    subset = [("- %s [%s](%s)") % (item[0], item[1], item[0]) for item in subset]
    # converte para string
    string = "\n".join(subset)
    contents = ('---\ntitle: Notas\n---\n'
                    '## Recentes:\n%s\n\n***\n'
                    '## [Busca](android-app://jp.sblo.pandora.aGrep)\n') % (string)
    index_android = open(os.path.join(folder, ".index_android.txt"), "w", encoding="utf8")
    index_android.write(contents)
    index_android.close()


# ----------------------------------------------------------
# Funções de atualização
# ----------------------------------------------------------

def update_index(notes_folder, index_folder, rebuild = False, get_body_tags = False):
    if rebuild:
        timestamp = 0
        index_old = None
    else:
        timestamp = open(os.path.join(index_folder, ".index.zktimestamp"), "r").read()
        timestamp = float(timestamp)
        with open(os.path.join(index_folder, ".index.zkdata"), 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            index_old = list(reader)
    modified = get_modified_notes(notes_folder, timestamp)
    if len(modified) > 0:
        index, count_new, count_updated = get_notes_metadata(modified, index_old, get_body_tags)
        with open(os.path.join(index_folder, ".index.zkdata"), "w+", newline="", encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(index)
        index_android(index, notes_folder)
    else:
        count_new = 0
        count_updated = 0
    log(index_folder, count_new, count_updated)



def update_links(notes_folder, index_folder, rebuild = False):
    if rebuild:
        timestamp = 0
        linklist_old = None
    else:
        timestamp = open(os.path.join(index_folder, ".links.zktimestamp"), "r").read()
        timestamp = float(timestamp)
        with open(os.path.join(index_folder, ".links.zkdata"), 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            linklist_old = list(reader)
    modified = get_modified_notes(notes_folder, timestamp)
    if len(modified) > 0:
        linklist = get_links(modified, linklist_old)
        with open(os.path.join(index_folder, ".links.zkdata"), "w+", newline="", encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(linklist)
    log(index_folder, 0, 0, True)