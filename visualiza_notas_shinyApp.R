#  Shiny app para visualizar rede de notas
#
# Deve ser rodado shell com argumento indicando diretório de notas
#
# Interações:
# - Busca de notas
# - Exibe/esconde nodes de ref bibliograficas não fichadas


library(shiny)
library(visNetwork)
library(readr)
library(dplyr)

# Captura argumento com diretório de notas
args <- commandArgs(trailingOnly = TRUE)
folder <- args[1]


# 1. Organiza dados ----
## Load 
nodes <- read_csv(file.path(folder, ".index.zkdata"), col_types = "cccd") 
edges <- read_csv(file.path(folder, ".links.zkdata"), col_types = "ccc")

# Cria nodes de ref biblio e define grupos 
# Grupo 0 = notas com id numérico
# Grupo 1 = fichamentos 
# Grupo 2 = refs bibliográficas não fichadas
refs <- edges %>% 
        select(to) %>%
        filter((!to %in% nodes$id) & 
                 stringr::str_detect(edges$to, "^[A-Za-z]")) %>%
        unique() %>%
        transmute(id=to, title=id, group=2)

nodes<- nodes %>% 
  mutate(id=as.character(id),
         group=case_when(startsWith(id, "2") ~ 0,
                         TRUE ~ 1)) %>%
  bind_rows(refs) %>% 
  unique()

## Mantém apenas links para notas em nodes
edges <- edges[edges$to %in% nodes$id,]

## Label: se é fichamento, label = id; caso contrário, limita título a 
## 75 characters e quebra em três linhas
nodes <- nodes %>%
  mutate(label = case_when(
    startsWith(id, "2") ~ gsub('(.{1,25})(\\s|$)', '\\1\n', 
                               substr(title, 1, 75)),
    TRUE ~ id
  ))


## Link para nota (depende de pacote "subl protocol" no Sublime)
## e texto completo embutido na tooltip
nodes <- nodes %>%
  mutate(title = paste0('<p><a href="subl://', file.path(folder,id), 
                        '.md"><b>', id, ' ',  title, 
                        '</b></a></p><div><object data="data/',
                        id,
                        '.md"  width="600"></object></div>')
  )



## Substitui separador de tags
nodes <- nodes %>%
  mutate(tags = gsub(";", ",", tags))

## CSS para tooltip
tooltip_style <- 'position: fixed; visibility: hidden;
                  padding: 5px; white-space: normal;
                  font-family: verdana; font-size: 14px;
                  background-color: rgb(245, 244, 237);
                  border-radius: 3px; border: 1px solid rgb(128, 128, 116);
                  box-shadow: rgba(0, 0, 0, 0.2) 3px 3px 10px; max-width: 600px;
                  word-wrap: break-word'



# 2. Shiny app

# Bancos alternativos para exibir/esconde grupo 2
nodes_comrefs <- nodes 
edges_comrefs <- edges

nodes_semrefs <- nodes %>% filter(group != 2)
edges_semrefs <- edges %>% filter(to %in% nodes_semrefs$id)


# Lista para busca
focuslist_comrefs <- setNames(as.list(nodes_comrefs$id), 
                              paste0(nodes_comrefs$id," ", nodes_comrefs$label))

focuslist_semrefs <- setNames(as.list(nodes_semrefs$id), 
                              paste0(nodes_semrefs$id," ", nodes_semrefs$label))

# Adiciona acesso a arquivos
addResourcePath(prefix = 'data', directoryPath = folder)

ui <- fluidPage(
  # App title 
  titlePanel("Rede de Notas"),

  fluidRow(
    # Input: busca de notas
    column(
          selectInput("focusid", "Buscar nota", c("Digite.." = "", focuslist_comrefs), width="100%"),
          width=9
          ),
    column(
      checkboxInput("refs", label = "Mostrar referências bibliográficas", value = TRUE),
      width=3
    )
          ),
  
  
  fluidRow(
    # Output: 
    column(
           visNetworkOutput("network", height = "600px"), 
           width=12
          )
          )
)


server <- function(input, output, session) {
  
  output$network <- renderVisNetwork({
    visNetwork(nodes_comrefs, edges_comrefs)  %>%
      visIgraphLayout(randomSeed = 1103) %>%
      visOptions(selectedBy = list(variable = "tags", multiple = T), 
                 highlightNearest = list(enabled = T, degree = 1,  algorithm="hierarchical")) %>%
      visEdges(arrows = "to") %>% 
      visInteraction(tooltipDelay = 100) %>%
      visNodes(font="12px arial black") %>%
      visGroups(groupname = "0", color="#97C2FC") %>%
      visGroups(groupname = "1", color="#6987B0") %>%
      visGroups(groupname = "2", color="#6987B0")
    

  })
  
  observe({   
    visNetworkProxy("network") %>%
    visFocus(id = input$focusid, 
             scale = 1,
             animation =list(duration = 200, easingFunction = "easeInOutQuad"))
  })
  
  observe({
    if (input$refs){
      output$network <- renderVisNetwork({
        visNetwork(nodes_comrefs, edges_comrefs)  %>%
          visIgraphLayout(randomSeed = 1103) %>%
          visOptions(selectedBy = list(variable = "tags", multiple = T), 
                     highlightNearest = list(enabled = T, degree = 1,  algorithm="hierarchical")) %>%
          visEdges(arrows = "to") %>% 
          visInteraction(tooltipDelay = 100) %>%
          visNodes(font="12px arial black") %>%
          visGroups(groupname = "0", color="#97C2FC") %>%
          visGroups(groupname = "1", color="#6987B0") %>%
          visGroups(groupname = "2", color="#6987B0") 
        
      })
      
      
      updateSelectInput(session, "focusid",
                        choices = c("Digite.." = "", focuslist_comrefs))
      
    } else {
      visNetworkProxy("network") %>%
        visRemoveNodes(nodes$id[nodes$group==2])
      
      updateSelectInput(session, "focusid",
                        choices =c("Digite.." = "", focuslist_semrefs))

    }
  })
}

runApp(list(ui=ui, server=server), host="0.0.0.0", port=1234, launch.browser = T)
