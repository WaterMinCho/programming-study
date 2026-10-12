def my_dfs(graph, start_node):
    stack = list()
    visited = list()

    stack.append(start_node)

    while stack:
        node = stack.____()

        if node ____ visited:
            stack.extend(____(graph[node]))
            visited.append(node)

    return visited


my_graph = {
    "A": ["B", "C", "D"],
    "B": ["A", "E"],
    "C": ["A", "F", "G"],
    "D": ["A", "H"],
    "E": ["B", "I"],
    "F": ["C", "J"],
    "G": ["C"],
    "H": ["D"],
    "I": ["E"],
    "J": ["F"],
}
g1 = {1: [2, 3, 4], 2: [1, 5], 3: [1, 6], 4: [1, 6], 5: [2, 6], 6: [3, 4, 5]}
