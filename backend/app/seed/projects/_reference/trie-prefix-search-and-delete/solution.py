class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_word = False


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            node = node.children.setdefault(ch, TrieNode())
        node.is_word = True

    def _find(self, word: str):
        node = self.root
        for ch in word:
            node = node.children.get(ch)
            if node is None:
                return None
        return node

    def search(self, word: str) -> bool:
        node = self._find(word)
        return node is not None and node.is_word

    def starts_with(self, prefix: str) -> bool:
        return self._find(prefix) is not None

    def delete(self, word: str) -> bool:
        path = [self.root]
        node = self.root
        for ch in word:
            node = node.children.get(ch)
            if node is None:
                return False
            path.append(node)

        if not node.is_word:
            return False
        node.is_word = False

        # Prune from the leaf back up, but stop the moment a node is still
        # needed: either it is a word boundary itself, or it still has
        # other children.
        for i in range(len(word) - 1, -1, -1):
            parent = path[i]
            child = path[i + 1]
            if child.children or child.is_word:
                break
            del parent.children[word[i]]
        return True
