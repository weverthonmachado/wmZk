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
library(igraph)
library(qgraph)

## Funções para criar grafico e coordenadas igraph, com e sem refs
cria_graph <- function(e, v){
  
  g <- graph_from_data_frame(e, 
                             vertices = mutate(v, name=id))
  g <-  g %>% 
    set_vertex_attr("size", 
                    value = scales::rescale(degree(g), 
                                            c(20,45)))
  return(g)
}

obtem_coord <- function(g){
  coords <- qgraph.layout.fruchtermanreingold(
    as_edgelist(g, names = F), 
    vcount=vcount(g), 
    area=6*(vcount(g)^2),
    repulse.rad=(vcount(g)^3)
  )
  
  return(coords)
  
}



# Captura argumento com diretório de notas
args <- commandArgs(trailingOnly = TRUE)
index_folder <- args[1]
notes_folder <- args[2]

# 1. Organiza dados ----
## Load 
nodes <- read_csv(file.path(index_folder, ".index.zkdata"), col_types = "cccd") 
edges <- read_csv(file.path(index_folder, ".links.zkdata"), col_types = "ccc")

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
  mutate(title = paste0('<p><a href="subl://', file.path(notes_folder, id), 
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

# Graficos com e sem referencias
g_comrefs <- cria_graph(edges_comrefs, nodes_comrefs)
coord_comrefs <- obtem_coord(g_comrefs)

g_semrefs <- cria_graph(edges_semrefs, nodes_semrefs)
coord_semrefs <- obtem_coord(g_semrefs)

# Adiciona acesso a arquivos
addResourcePath(prefix = 'data', directoryPath = notes_folder)

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
      checkboxInput("refs", label = "Mostrar referencias bibliograficas", value = TRUE),
      width=3
    )
  ),
  
  
  fluidRow(
    # Output: 
    column(
      visNetworkOutput("network", height = "800px"), 
      width=12
    )
  )
)


server <- function(input, output, session) {
  
  
  output$network <- renderVisNetwork({
    visIgraph(g_semrefs, idToLabel=F)  %>%
      visIgraphLayout("layout.norm", layoutMatrix = coord_semrefs) %>% 
      visOptions(selectedBy = list(variable = "tags", multiple = T), 
                 highlightNearest = list(enabled = T, degree = 1,  algorithm="hierarchical")) %>%
      visEdges(arrows = "to",
               color = list(color="#9c9c9c", highlight="#6987B0")) %>% 
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
               animation =list(duration = 200, easingFunction = "easeInOutQuad")) %>%
      visSelectNodes(id = input$focusid)
  })
  
  observe({
    if (input$refs){
      output$network <- renderVisNetwork({
        visIgraph(g_comrefs, idToLabel=F)  %>%
          visIgraphLayout("layout.norm", layoutMatrix = coord_comrefs) %>% 
          visOptions(selectedBy = list(variable = "tags", multiple = T), 
                     highlightNearest = list(enabled = T, degree = 1,  algorithm="hierarchical")) %>%
          visEdges(arrows = "to",
                   color = list(color="#9c9c9c", highlight="#6987B0")) %>% 
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



# TESTE de ego graph
# visIgraph(
#   make_ego_graph(g_comrefs, 
#                  order=1, 
#                  nodes=50)[[1]], 
#   idToLabel = F) %>% 
#   visInteraction(tooltipDelay = 100) %>%
#   visNodes(font="12px arial black") %>%
#   visGroups(groupname = "0", color="#97C2FC") %>%
#   visGroups(groupname = "1", color="#6987B0") %>%
#   visGroups(groupname = "2", color="#6987B0")


