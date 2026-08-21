class BSTNode:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None


class BST:
    def __init__(self):
        self.root = None

    def insert(self, value) -> None:
        if self.root is None:
            self.root = BSTNode(value)
            return
        node = self.root
        while True:
            if value < node.value:
                if node.left is None:
                    node.left = BSTNode(value)
                    return
                node = node.left
            elif value > node.value:
                if node.right is None:
                    node.right = BSTNode(value)
                    return
                node = node.right
            else:
                return  # no duplicates

    def contains(self, value) -> bool:
        node = self.root
        while node is not None:
            if value == node.value:
                return True
            node = node.left if value < node.value else node.right
        return False

    def inorder(self) -> list:
        result = []

        def walk(node):
            if node is None:
                return
            walk(node.left)
            result.append(node.value)
            walk(node.right)

        walk(self.root)
        return result

    def delete(self, value) -> None:
        self.root = self._delete(self.root, value)

    def _delete(self, node, value):
        if node is None:
            return None

        if value < node.value:
            node.left = self._delete(node.left, value)
        elif value > node.value:
            node.right = self._delete(node.right, value)
        else:
            # Found the node to delete.
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            # Two children: pull up the inorder successor (smallest value
            # in the right subtree), then delete that successor from the
            # right subtree — it is guaranteed to have at most one child.
            successor = node.right
            while successor.left is not None:
                successor = successor.left
            node.value = successor.value
            node.right = self._delete(node.right, successor.value)

        return node
