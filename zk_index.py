'''
WM - ZETTELKASTEN

Script para manter índice de notas em plain text.

'''
import os
import re
import sys
import markdown
import time
import pandas as pd
from itertools import islice
pd.set_option('display.max_colwidth', -1)


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


def get_notes_metadata(filelist, index=None):
    '''
    Loop por `filelist` e cria um pandas dataframe com metadados das notas.
    Se um dataframe `index` é fornecido, registros são acrescentados ou 
    atualizados.
    Retorna o dataframe, número de notas criadas e número de notas atualizadas.
    '''
    if index is None:
        index = pd.DataFrame([], columns=['id', 'title', 'tags', 'modified'])
    md = markdown.Markdown(extensions = ['meta'])
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
        tags = ";".join(tags)
        modified = os.stat(file).st_mtime
        # Se id já existe em index, atualiza title e tags;
        # se não, acrescenta linha
        if id in pd.Series(index['id']).values:
            index.loc[index["id"]==id, ["title"]] = title
            index.loc[index["id"]==id, ["tags"]] = tags
            index.loc[index["id"]==id, ["modified"]] = modified
            count_update += 1
        else:
            new_note = pd.DataFrame([[id, title, tags, modified]],
                                    columns=['id', 'title', 'tags', 'modified'])
            index = index.append(new_note)
            count_new += 1
    index = index.sort_values("modified", ascending=False)
    return index, count_new, count_update


def get_links(filelist, linklist=None):
    '''
    Loop por `filelist` e coleta links para outras notas. Além dos links no 
    formato wiki `[[201901131249]]`, também identifica links com o formato 
    `@citekey` para notas bibliográficas.
    Retorna pandas dataframe com colunas 'from', 'to' e 'fromtitle'. 
    Caso o dataframe `linklist` seja fornecido, links são acrescentados ou removidos.
    ''' 
    if linklist is None:
        linklist = pd.DataFrame([], columns=['from', 'to', 'fromtitle'])
    for file in filelist:
        text = open(file, "r", encoding="utf8").read()
        id = re.findall(r"id:\s*(\d{12}|[^\s\d]+\d{4}\w*)", text)[0]
        fromtitle =  re.findall(r"\ntitle:\s*(.*)\n", text)[0].strip("'").strip('"')
        # Exclui da linklist os registros anteriores desta nota
        linklist = linklist.loc[linklist["from"]!=id]
        found_links = re.findall(r"(?<=\[\[)\s*\d{12}\s*(?=\]\])|(?<=@)[^\s\d]+\d{4}\w*", text)
        if len(found_links) > 0:
            found_links_df = pd.DataFrame([], columns=['from', 'to', 'fromtitle'])
            for link in found_links:
                # Ignora referências à própria nota (geralmente em notas bibliográficas)
                if link != id:
                    new_link = pd.DataFrame([[id, link, fromtitle]], columns=['from', 'to', 'fromtitle'])
                    found_links_df = found_links_df.append(new_link)
                    found_links_df = found_links_df.drop_duplicates()
            linklist = linklist.append(found_links_df)
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
        logfile = open(os.path.join(folder, ".zklog.txt"), "a", encoding="utf8")
        logfile.write(message)
        logfile.close()

    timestamp.write(str(now))
    timestamp.close()
    print(message)

def index_android(index, folder):
    '''
    Cria índice para uso do aplicativo Epsilon notes no Android
    '''
    # seleciona apenas id e titulo
    subset = index[['id', 'title']]
    # seleciona primeiras 10 linhas (ou seja, notas mais recentes)
    subset = subset[:10]
    # converte para string, sem nomes de colunas nem index
    string = subset.to_string(header=False, index=False)
    # cria lista de links com sintaxe markdown
    links = re.sub('(\d{12}|\w*\d{4}\w{0,1})\s*(.*)', "- \\1 [\\2](\\1)  ", string)
    contents = ('---\ntitle: Notas\n---\n'
                    '## Recentes:\n%s\n\n***\n'
                    '## [Busca](android-app://jp.sblo.pandora.aGrep)\n') % (links)
    index_android = open(os.path.join(folder, ".index_android.txt"), "w", encoding="utf8")
    index_android.write(contents)
    index_android.close()


# ----------------------------------------------------------
# Roda funções
# ----------------------------------------------------------

FOLDER = "C:/Dropbox/notas"

# Se tem argumento -links, coleta links em vez de metadata
# Se tem argumento -rebuild, processa todas as notas e cria index
# ou linklist do zero
if "-links" in sys.argv:
    if "-rebuild" in sys.argv:
        timestamp = 0
        linklist_old = None
    else:
        timestamp = open(os.path.join(FOLDER, ".links.zktimestamp"), "r").read()
        timestamp = float(timestamp)
        linklist_old = pd.read_csv(os.path.join(FOLDER, ".links.zkdata"), encoding="utf8")
    modified = get_modified_notes(FOLDER, timestamp)
    if len(modified) > 0:
        linklist = get_links(modified, linklist_old)
        linklist.to_csv(os.path.join(FOLDER, ".links.zkdata"), index=False)
        log(FOLDER, 0, 0, True)
else:
    if "-rebuild" in sys.argv:
        timestamp = 0
        index_old = None
    else:
        timestamp = open(os.path.join(FOLDER, ".index.zktimestamp"), "r").read()
        timestamp = float(timestamp)
        index_old = pd.read_csv(os.path.join(FOLDER, ".index.zkdata"), encoding="utf8")
    modified = get_modified_notes(FOLDER, timestamp)
    if len(modified) > 0:
        index, count_new, count_updated = get_notes_metadata(modified, index_old)
        index.to_csv(os.path.join(FOLDER, ".index.zkdata"), index=False)
        index_android(index, FOLDER)
        log(FOLDER, count_new, count_updated)