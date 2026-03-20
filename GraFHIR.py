import requests
import json
import os
from urllib.parse import urlparse
import webbrowser

# --- Configuración ---
FHIR_VERSION = "R4"
FHIR_SPEC_URL = f"https://hl7.org/fhir/{FHIR_VERSION}"
CACHE_DIR = "./fhir_definitions"
OUTPUT_HTML_FILE = "reporte_referencias_fhir.html"

# --- Matriz de Categorización de Recursos FHIR ---
RESOURCE_CATEGORIES = {
    "Clínica": [
        'Patient', 'Encounter', 'Observation', 'Condition', 'Procedure', 
        'AllergyIntolerance', 'CarePlan', 'FamilyMemberHistory', 
        'ClinicalImpression', 'Immunization'
    ],
    "Financiera": [
        'Claim', 'ClaimResponse', 'Coverage', 'CoverageEligibilityRequest', 
        'CoverageEligibilityResponse', 'ExplanationOfBenefit', 'Invoice', 
        'Account', 'ChargeItem'
    ],
    "Administrativa y de Flujo de Trabajo": [
        'Appointment', 'Schedule', 'Slot', 'Task', 'Practitioner', 
        'Organization', 'Location', 'RelatedPerson', 'EpisodeOfCare', 
        'HealthcareService'
    ],
    "Diagnóstica": [
        'DiagnosticReport', 'ImagingStudy', 'Specimen', 'Media', 'Observation'
    ],
    "Medicamentos": [
        'Medication', 'MedicationRequest', 'MedicationAdministration', 
        'MedicationStatement', 'MedicationKnowledge', 'Immunization'
    ],
    "Base y Conformidad": [
        'StructureDefinition', 'ValueSet', 'CodeSystem', 'CapabilityStatement', 
        'SearchParameter', 'OperationDefinition', 'ImplementationGuide', 
        'StructureMap', 'ConceptMap'
    ]
}

def get_all_fhir_resources():
    """
    Descarga y cachea la lista de todos los recursos FHIR R4 desde la especificación.
    Devuelve una lista de nombres de recursos.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, "resourcelist.json")

    if os.path.exists(cache_file):
        print("Cargando lista de recursos desde caché local...")
        with open(cache_file, 'r', encoding='utf-8') as f:
            bundle = json.load(f)
    else:
        # Se construye una URL específica para la versión de FHIR para evitar redirecciones (como la 300 Multiple Choices)
        # que pueden fallar en redes corporativas con proxies.
        resourcelist_url = f"https://hl7.org/fhir/{FHIR_VERSION}/resourcelist.json"
        print(f"Descargando lista de todos los recursos FHIR R4 desde {resourcelist_url}...")
        try:
            # Se añade allow_redirects=True para mayor robustez.
            response = requests.get(resourcelist_url, timeout=30, headers={'Accept': 'application/json'}, allow_redirects=True)
            response.raise_for_status()
            bundle = response.json()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(bundle, f, indent=2)
            print("Lista de recursos guardada en caché.")
        except requests.exceptions.JSONDecodeError as e:
            print(f"Error al decodificar la respuesta JSON desde {resourcelist_url}: {e}")
            print("La respuesta recibida no es un JSON válido (puede ser un error de red o un proxy).")
            print(f"Inicio de la respuesta recibida (primeros 500 caracteres):\n---\n{response.text[:500]}\n---")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Error de red al descargar la lista de recursos desde {resourcelist_url}: {e}")
            return []
        except Exception as e:
            print(f"Error al descargar la lista de recursos: {e}")
            return []

    resource_types = []
    if bundle.get('resourceType') == 'Bundle' and 'entry' in bundle:
        for entry in bundle.get('entry', []):
            resource = entry.get('resource', {})
            if resource.get('resourceType') == 'Basic':
                # El nombre del recurso está en una extensión
                for extension in resource.get('extension', []):
                    if extension.get('url') == 'http://hl7.org/fhir/StructureDefinition/resource-code':
                        code = extension.get('valueCode')
                        if code:
                            resource_types.append(code)
                        break
    
    # Filtrar recursos abstractos que no tienen una definición de perfil directa
    # y que causarían errores 404.
    abstract_resources = {'Resource', 'DomainResource', 'Element', 'BackboneElement'}
    final_list = sorted([r for r in list(set(resource_types)) if r not in abstract_resources])
    return final_list

def get_structure_definition(resource_type: str):
    """
    Descarga y cachea la StructureDefinition para un tipo de recurso FHIR.
    Devuelve el contenido JSON.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(CACHE_DIR, f"{resource_type}.profile.json")

    # 1. Intentar leer desde la caché local
    if os.path.exists(cache_file):
        print(f"Cargando '{resource_type}' desde caché local...")
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 2. Si no está en caché, descargar desde la web
    print(f"Descargando StructureDefinition para '{resource_type}' desde {FHIR_SPEC_URL}...")
    url = f"{FHIR_SPEC_URL}/{resource_type}.profile.json"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Guardar en caché para uso futuro
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"'{resource_type}' guardado en caché.")
        return data
    except requests.exceptions.JSONDecodeError as e:
        print(f"Error al decodificar la respuesta JSON para '{resource_type}' desde {url}: {e}")
        print("La respuesta recibida no es un JSON válido (puede ser un error de red o un proxy).")
        print(f"Inicio de la respuesta recibida (primeros 500 caracteres):\n---\n{response.text[:500]}\n---")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Error: No se encontró la StructureDefinition para '{resource_type}' en la especificación FHIR {FHIR_VERSION}.")
        else:
            print(f"Error HTTP al descargar la definición: {e}")
    except requests.exceptions.RequestException as e:
        print(f"Error de red al descargar la definición para '{resource_type}' desde {url}: {e}")
    except Exception as e:
        print(f"Ocurrió un error inesperado: {e}")
    
    return None

def analyze_references(resource_type: str):
    """
    Analiza la StructureDefinition de un recurso y extrae información sobre
    sus referencias a otros recursos. Devuelve una lista de diccionarios.
    """
    structure_def = get_structure_definition(resource_type)
    if not structure_def:
        return [] # Return empty list on failure

    print(f"Analizando referencias para el Recurso: {resource_type}")

    if 'snapshot' not in structure_def or 'element' not in structure_def['snapshot']:
        print("Error: El formato de StructureDefinition no es el esperado (falta 'snapshot.element').")
        return []

    results = []
    for element in structure_def['snapshot']['element']:
        # Buscamos elementos que sean de tipo 'Reference'
        element_types = element.get('type', [])
        is_reference = any(t.get('code') == 'Reference' for t in element_types)

        if is_reference:
            path = element.get('path', 'N/A')
            min_card = element.get('min', 0)
            max_card = element.get('max', '*')
            
            obligatorio = "Sí" if min_card > 0 else "No"
            cardinalidad = f"{min_card}..{max_card}"
            
            target_profiles = []
            for t in element_types:
                if t.get('code') == 'Reference':
                    for profile_url in t.get('targetProfile', []):
                        parsed_url = urlparse(profile_url)
                        resource_name = os.path.basename(parsed_url.path)
                        target_profiles.append(resource_name)
            
            recursos_referenciados = ", ".join(sorted(list(set(target_profiles)))) or "Cualquiera (Any)"

            results.append({
                "recurso_solicitado": resource_type,
                "tag": path,
                "obligatoriedad": obligatorio,
                "cardinalidad": cardinalidad,
                "recurso_referenciado": recursos_referenciados
            })
    
    if not results:
        print(f"No se encontraron referencias a otros recursos en la definición de '{resource_type}'.")
    
    return results

def generate_interactive_graph_report(all_data, resource_categories, all_resource_types, filename):
    """
    Genera un archivo HTML con un grafo interactivo de vis.js a partir de los datos
    y lo abre en el navegador.
    """
    nodes = []
    edges = []
    
    # Crear un mapeo inverso de Recurso -> [Categorías]
    resource_to_category_map = {}
    for category, resources in resource_categories.items():
        for resource in resources:
            if resource not in resource_to_category_map:
                resource_to_category_map[resource] = []
            resource_to_category_map[resource].append(category)
    
    # 1. Identificar todos los nodos únicos.
    # Empezamos con todos los recursos que se intentaron procesar para asegurar que los "nodos isla" (sin conexiones) aparezcan.
    node_ids = set(all_resource_types)
    for row in all_data:
        # El 'recurso_solicitado' ya está en el set, solo necesitamos agregar los targets que podrían ser recursos no procesados directamente.
        targets = [t.strip() for t in row['recurso_referenciado'].split(',') if t.strip() and t.strip() != 'Any']
        for target in targets:
            node_ids.add(target)

    # 2. Crear la lista de nodos para vis.js
    for node_id in sorted(list(node_ids)):
        nodes.append({
            "id": node_id,
            "label": node_id,
            "shape": "box",
            "color": {
                "background": '#EAEAEA', # Color base para todos
                "border": '#BDBDBD',
                "highlight": { "background": '#EAEAEA', "border": '#e15759', "borderWidth": 2 },
            },
            "font": {"color": '#343434'}
        })

    # 3. Crear la lista de aristas (relaciones) para vis.js
    for row in all_data:
        source_node = row['recurso_solicitado']
        target_resources_str = row['recurso_referenciado']
        
        targets = [t.strip() for t in target_resources_str.split(',') if t.strip() and t.strip() != 'Any']
        
        for target_node in targets:
            if target_node in node_ids:
                is_mandatory = row['obligatoriedad'] == 'Sí'
                cardinality_label = row['cardinalidad']
                tag_path = row['tag']
                
                # Usar la última parte del path para una etiqueta más limpia
                edge_label = f"{tag_path.split('.')[-1]}\n[{cardinality_label}]"
                
                # Tooltip con información completa
                tooltip = (f"De: {source_node}\nA: {target_node}\n"
                           f"Ruta: {tag_path}\n"
                           f"Obligatorio: {row['obligatoriedad']}\n"
                           f"Cardinalidad: {cardinality_label}")

                edges.append({
                    "from": source_node,
                    "to": target_node,
                    "label": edge_label,
                    "dashes": not is_mandatory, # True para discontinuo (opcional), False para continuo (obligatorio)
                    "arrows": "to",
                    "font": {"align": "horizontal"},
                    "title": tooltip
                })

    # 4. Generar el contenido del archivo HTML
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Grafo de Relaciones FHIR</title>
        <script type="text/javascript" src="https://visjs.github.io/vis-network/standalone/umd/vis-network.min.js"></script>
        <style>
            html, body {{ font-family: sans-serif; width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; }}
            h1 {{ position: absolute; top: 10px; left: 10px; z-index: 10; color: #333; background-color: rgba(255,255,255,0.8); padding: 5px 10px; border-radius: 5px;}}
            #mynetwork {{ width: 100%; height: 100%; border: 1px solid lightgray; }}
            
            .filter-toggle {{
                position: absolute;
                right: 20px;
                padding: 8px 12px;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
                cursor: pointer;
                z-index: 30;
                font-size: 13px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .filter-toggle:hover {{ background-color: #f0f0f0; }}
            #resource-filter-toggle {{ top: 20px; }}
            #category-filter-toggle {{ top: 70px; }}

            .filter-panel {{
                position: absolute;
                right: 10px;
                width: 250px;
                max-height: 80vh;
                overflow-y: auto;
                background-color: rgba(255, 255, 255, 0.95);
                border: 1px solid #ddd;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                z-index: 20;
                padding: 10px;
                font-size: 13px;
                transition: transform 0.3s ease-in-out, visibility 0.3s;
                transform: translateX(120%);
                visibility: hidden;
            }}
            #resource-filter {{ top: 20px; max-height: 40vh; }}
            #category-filter {{ top: 120px; max-height: 40vh; }}

            .filter-panel.visible {{
                transform: translateX(0);
                visibility: visible;
            }}

            .filter-panel h3 {{ margin-top: 0; font-size: 16px; border-bottom: 1px solid #ccc; padding-bottom: 5px; }}
            .filter-options-container div {{
                display: flex;
                align-items: center;
                margin-bottom: 5px;
            }}
            .filter-options-container label {{
                margin-left: 5px;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                cursor: pointer;
            }}

            #control-panel {{
                position: absolute;
                top: 120px;
                left: 10px;
                background-color: rgba(255, 255, 255, 0.95);
                border: 1px solid #ddd;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                z-index: 20;
                padding: 10px;
                font-size: 14px;
            }}
            #control-panel h3 {{ margin-top: 0; font-size: 16px; }}
            .control-item {{ margin-bottom: 15px; }}
            .control-item label {{ display: block; margin-bottom: 5px; font-weight: bold; }}
            .control-item input[type=range] {{ width: 100%; }}
        </style>
    </head>
    <body>
        <h1>Grafo de Relaciones FHIR</h1>

        <div id="resource-filter-toggle" class="filter-toggle" onclick="toggleFilterMenu('resource-filter')">&#x1F5B3;&#xFE0E; Recursos</div>
        <div id="category-filter-toggle" class="filter-toggle" onclick="toggleFilterMenu('category-filter')">&#x1F4C2; Categorías</div>

        <div id="resource-filter" class="filter-panel">
            <h3>Mostrar/Ocultar Recursos</h3>
            <div id="resource-filter-options" class="filter-options-container"></div>
        </div>
        <div id="category-filter" class="filter-panel">
            <h3>Mostrar/Ocultar Categorías</h3>
            <div id="category-filter-options" class="filter-options-container"></div>
        </div>

        <div id="control-panel">
            <h3>Controles</h3>
            <div class="control-item">
                <label for="edge-label-toggle">Etiquetas de Aristas</label>
                <input type="checkbox" id="edge-label-toggle" checked onchange="toggleEdgeLabels(this.checked)"> Mostrar
            </div>
            <div class="control-item">
                <label for="edge-font-slider">Tamaño de Letra</label>
                <input type="range" id="edge-font-slider" min="0" max="20" value="10" oninput="updateEdgeFontSize(this.value)">
            </div>
            <div class="control-item">
                <label for="physics-toggle">Simulación de Físicas</label>
                <input type="checkbox" id="physics-toggle" checked onchange="togglePhysics(this.checked)"> Activar
            </div>
        </div>

        <div id="mynetwork"></div>
        <script type="text/javascript">
            var container = document.getElementById('mynetwork');
            var nodes = new vis.DataSet({json.dumps(nodes, indent=4)});
            var edges = new vis.DataSet({json.dumps(edges, indent=4)});
            const resourceToCategoryMap = {json.dumps(resource_to_category_map, indent=4)};
            var data = {{ nodes: nodes, edges: edges }};
            var options = {{
                layout: {{
                    hierarchical: {{
                        enabled: false // Usamos un layout de física para mejor distribución
                    }}
                }},
                physics: {{
                    enabled: true // Inicia activado para renderizar el grafo
                }},
                interaction: {{
                    dragNodes: true,
                    hover: true
                }},
                edges: {{
                    font: {{
                        size: 10 // Tamaño inicial de la fuente de las aristas
                    }},
                    smooth: {{
                        type: 'cubicBezier',
                        forceDirection: 'horizontal',
                        roundness: 0.4
                    }}
                }}
            }};
            var network = new vis.Network(container, data, options);

            // --- State Management ---
            let visibleResources = new Set(nodes.getIds());
            let visibleCategories = new Set(Object.keys({json.dumps(resource_categories, indent=4)}));
            let areEdgeLabelsVisible = true;
            let currentEdgeFontSize = 10;

            // --- UI & Control Functions ---
            function toggleFilterMenu(menuId) {{
                document.getElementById(menuId).classList.toggle('visible');
            }}

            function toggleEdgeLabels(isVisible) {{
                areEdgeLabelsVisible = isVisible;
                document.getElementById('edge-font-slider').disabled = !isVisible;
                network.setOptions({{
                    edges: {{
                        font: {{
                            size: isVisible ? currentEdgeFontSize : 0
                        }}
                    }}
                }});
            }}

            function updateEdgeFontSize(size) {{
                currentEdgeFontSize = parseInt(size, 10);
                if (areEdgeLabelsVisible) {{
                    network.setOptions({{
                        edges: {{
                            font: {{
                                size: currentEdgeFontSize
                            }}
                        }}
                    }});
                }}
            }}

            function togglePhysics(isEnabled) {{
                network.setOptions({{
                    physics: {{
                        enabled: isEnabled
                    }}
                }});
            }}

            // --- Filtering Logic ---
            function updateNodeVisibility() {{
                const nodesToUpdate = [];
                nodes.getIds().forEach(nodeId => {{
                    const node = nodes.get(nodeId);
                    const nodeCategories = resourceToCategoryMap[node.id] || [];
                    const belongsToVisibleCategory = nodeCategories.some(cat => visibleCategories.has(cat));
                    const isResourceVisible = visibleResources.has(node.id);

                    // Un nodo es visible si su tipo de recurso está marcado Y (no tiene categorías O pertenece al menos a una categoría marcada).
                    const shouldBeVisible = isResourceVisible && (nodeCategories.length === 0 || belongsToVisibleCategory);
                    const targetHiddenState = !shouldBeVisible;
                    const currentHiddenState = node.hidden || false; // Tratar 'undefined' como 'false'
                    if (currentHiddenState !== targetHiddenState) {{
                        nodesToUpdate.push({{ id: node.id, hidden: targetHiddenState }});
                    }}
                }});

                if (nodesToUpdate.length > 0) {{
                    nodes.update(nodesToUpdate);
                }}
            }}

            // --- Filter Population ---
            function populateResourceFilter() {{
                const container = document.getElementById('resource-filter-options');
                let html = '';
                nodes.getIds().sort().forEach(nodeId => {{
                    html += `
                        <div>
                            <input type="checkbox" id="check-res-${{nodeId}}" checked onchange="toggleResource('${{nodeId}}', this.checked)">
                            <label for="check-res-${{nodeId}}">${{nodeId}}</label>
                        </div>
                    `;
                }});
                container.innerHTML = html;
            }}

            function populateCategoryFilter() {{
                const container = document.getElementById('category-filter-options');
                let html = '';
                Object.keys({json.dumps(resource_categories, indent=4)}).sort().forEach(cat => {{
                    html += `
                        <div>
                            <input type="checkbox" id="check-cat-${{cat}}" checked onchange="toggleCategory('${{cat}}', this.checked)">
                            <label for="check-cat-${{cat}}">${{cat}}</label>
                        </div>
                    `;
                }});
                container.innerHTML = html;
            }}

            // --- Filter Event Handlers ---
            function toggleResource(nodeId, isVisible) {{
                isVisible ? visibleResources.add(nodeId) : visibleResources.delete(nodeId);
                updateNodeVisibility();
            }}

            function toggleCategory(category, isVisible) {{
                isVisible ? visibleCategories.add(category) : visibleCategories.delete(category);
                updateNodeVisibility();
            }}

            // --- Initial Setup ---
            populateResourceFilter();
            populateCategoryFilter();

            // Desactivar la física después de la estabilización inicial
            network.on("stabilizationIterationsDone", function () {{
              network.setOptions( {{ physics: false }} );
              document.getElementById('physics-toggle').checked = false; // Sincronizar UI
            }});
        </script>
    </body>
    </html>
    """

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        report_path = os.path.abspath(filename)
        print(f"\\nReporte gráfico generado exitosamente en: {report_path}")
        webbrowser.open_new_tab(f"file://{report_path}")

    except Exception as e:
        print(f"Error al generar o abrir el reporte HTML: {e}")

def main():
    print(f"Usando la especificación FHIR versión: {FHIR_VERSION}")
    print(f"Las definiciones se guardarán en el directorio: '{os.path.abspath(CACHE_DIR)}'")
    print("-" * 40)

    # Obtener todos los recursos FHIR en lugar de una lista fija
    try:
        all_resource_types = get_all_fhir_resources()
        if not all_resource_types:
            print("\nError Crítico: La lista de recursos FHIR está vacía.")
            print("Esto suele ocurrir por un problema de red al intentar descargar 'resourcelist.json' desde hl7.org.")
            print("Por favor, verifica tu conexión a internet e intenta ejecutar el script de nuevo.")
            return
        print(f"Se procesarán {len(all_resource_types)} tipos de recursos FHIR.")
    except Exception as e:
        print(f"No se pudo obtener la lista de recursos FHIR: {e}")
        return

    all_results = []
    for resource_type in all_resource_types:
        results = analyze_references(resource_type)
        all_results.extend(results)
        print("-" * 40)

    generate_interactive_graph_report(all_results, RESOURCE_CATEGORIES, all_resource_types, OUTPUT_HTML_FILE)

if __name__ == "__main__":
    main()
