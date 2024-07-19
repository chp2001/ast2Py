import ast
from enum import Enum
from typing import List, Dict, Any, TypeAlias, Union, Tuple
import sys
import warnings

def __recent_call_stack__(offset:int = 1, n:int = 3) -> List[str]:
    "Helper function to get information about the recent call stack"
    _offset = offset + 1 # Adjust for this function
    stack = [sys._getframe(i) for i in range(_offset, _offset + n)]
    return [f"{frame.f_code.co_name} in {frame.f_code.co_filename}:{frame.f_lineno}" for frame in stack]

# Improved version of NodeVisitor,
# Automatically passes relevant pathing information to the visitor methods
# (First, however, we define a new Enum class to store the specific traversal types)
class VisitType(Enum):
    """
    # VisitType

    Enum class to store the specific traversal types.
    Specifically used to help record the structure of a tree as it is traversed.

    Values: (Given an object as obj and an index(or key if not integer-indexed) as index)
    - ATTRIBUTE: Attribute access
        - Specifically, when the movement can be done through `.` or `getattr()`
        - e.g. `obj.index`, `{class instance}.index`, `getattr(obj, index)`
    - SUBSCRIPT: Subscript access
        - Only for classes with __getitem__ method like lists, dictionaries, etc.
        - e.g. `obj[index]`, `{list}[index]`, `obj.__getitem__(index)`
    - ATTR_SUBSCRIPT: Attribute and Subscript access
        - Used to combine the pair of accesses to skip representing a non-node storage object
        - For example, a FunctionDef will have its children within its `body` attribute, which is a list
        - For this one we need to remember both the attribute and the subscript access
        - Using object as obj, attribute as attr, and index as index:
        - e.g. `obj.attr[index]`, `{class instance}.attr[index]`, `getattr(obj, attr)[index]`
    """
    # Enum values
    ATTRIBUTE = 1
    """Attribute access"""
    SUBSCRIPT = 2
    """Subscript access"""
    ATTR_SUBSCRIPT = 3
    """Attribute and Subscript access"""

    __readable__ = {
        ATTRIBUTE: "Attribute",
        SUBSCRIPT: "Subscript",
        ATTR_SUBSCRIPT: "Attribute and Subscript"
    }

    index_type = Union[int, str, tuple['index_type', 'index_type']]

    @staticmethod
    def __attr_access__(obj: Any, attr: index_type) -> Any:
        """Attribute access"""
        if not hasattr(obj, attr):
            warnings.warn(f"Attribute '{attr}' not found in object of type '{type(obj)}'\n" + "\n".join(__recent_call_stack__()), RuntimeWarning)
        return getattr(obj, attr)
    
    @staticmethod
    def __subscript_access__(obj: Any, index: index_type) -> Any:
        """Subscript access"""
        if not hasattr(obj, "__getitem__"):
            warnings.warn(f"Object of type '{type(obj)}' does not support subscripting\n" + "\n".join(__recent_call_stack__()), RuntimeWarning)
        return obj[index]
    
    @staticmethod
    def __attr_subscript_access__(obj: Any, attr: index_type, index: index_type) -> Any:
        """Attribute and Subscript access"""
        return VisitType.__subscript_access__(VisitType.__attr_access__(obj, attr), index)
    
    def __call__(self, obj: Any, index: index_type) -> Any:
        """Call the respective access method based on the enum value"""
        if self == VisitType.ATTRIBUTE:
            return self.__attr_access__(obj, index)
        elif self == VisitType.SUBSCRIPT:
            return self.__subscript_access__(obj, index)
        elif self == VisitType.ATTR_SUBSCRIPT:
            attr, subscript = index
            return self.__attr_subscript_access__(obj, attr, subscript)
        else:
            raise ValueError(f"Invalid VisitType '{self}'\n" + "\n".join(__recent_call_stack__()))
        
    def __str__(self) -> str:
        """String representation of the VisitType"""
        return self.__readable__[self]
    
    def __repr__(self) -> str:
        """String representation of the VisitType"""
        return f"{self.__class__.__name__}.{self.value}"
    

# Now, modified NodeVisitor class that automatically passes pathing information
# We'll only define the methods that need to be modified to allow for pathing information
# The rest of the methods will be inherited from the ast.NodeVisitor class, or left to user implementation
class NodeVisitor(ast.NodeVisitor):
    """
    # NodeVisitor

    Modified version of the ast.NodeVisitor class that automatically passes pathing information
    to the visitor methods. This is done by using the VisitType enum class to store the
    specific traversal types. This helps record the structure of a tree as it is traversed.
    """
    def visit(self, node: ast.AST, path: List[VisitType.index_type] = []) -> ast.AST:
        """
        Visit a node and call the visitor function for it.

        Args:
        - node: The node to visit
        - path: The path to the node from the initially visited node
        Returns:
        - The final node after visiting all its children
        
        Note:
        - All children must be manually visited if any visit method is overridden, usually in the form of:
            `node = self.generic_visit(node, path)`
        """
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        if visitor.__code__.co_argcount < 3:
            raise ValueError(f"Visitor method '{method}' must have at least 3 arguments\n" \
                            + f"'{method} has {visitor.__code__.co_argcount}' arguments\n" \
                            + f"and was defined in '{visitor.__code__.co_filename}'\n" \
                            + "\n" + "\n".join(__recent_call_stack__()))
        return visitor(node, path)
    
    def generic_visit(self, node: ast.AST, path: List[VisitType.index_type]) -> ast.AST:
        """
        Called if no explicit visitor function exists for a node.

        Args:
        - node: The node to visit
        - path: The path to the node from the initially visited node
        Returns:
        - The final node after visiting all its children
        
        Note:
        - All children must be manually visited if any visit method is overridden, usually in the form of:
            `node = self.generic_visit(node, path)`
        """
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, ast.AST):
                        self.visit(item, path + [(VisitType.ATTR_SUBSCRIPT, (field, i))])
            elif isinstance(value, ast.AST):
                self.visit(value, path + [(VisitType.ATTRIBUTE, field)])
        return node
    
    def visit_Constant(self, node: ast.Constant, path: List[VisitType.index_type]) -> ast.AST:
        """
        Visit a Constant node.

        Args:
        - node: The Constant node to visit
        - path: The path to the node from the initially visited node
        Returns:
        - The final node after visiting all its children
        """
        value = node.value
        type_name = type(value).__name__
        if type_name is not None:
            method = 'visit_' + type_name
            try:
                visitor = getattr(self, method)
            except AttributeError:
                pass
            else:
                import warnings
                warnings.warn(f"{method} is deprecated; add visit_Constant",
                              DeprecationWarning, 2)
                return visitor(node, path)
        return self.generic_visit(node, path)


    
# Next is the improved version of the NodeTransformer class
# Just like the standard NodeTransformer, it inherits from NodeVisitor but with additional functionality
class NodeTransformer(NodeVisitor):
    """
    # NodeTransformer

    Modified version of the ast.NodeTransformer class that automatically passes pathing information
    to the visitor methods. This is done by using the VisitType enum class to store the
    specific traversal types. This helps record the structure of a tree as it is traversed.
    """
    def generic_visit(self, node: ast.AST, path: List[VisitType.index_type]) -> ast.AST:
        """
        Called if no explicit visitor function exists for a node.

        Args:
        - node: The node to visit
        - path: The path to the node from the initially visited node
        Returns:
        - The final node after visiting all its children

        Note:
        - All children must be manually visited if any visit method is overridden, usually in the form of:
            `node = self.generic_visit(node, path)`
        """
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                new_values = []
                for i, item in enumerate(value):
                    if isinstance(item, ast.AST):
                        item = self.visit(item, path + [(VisitType.ATTR_SUBSCRIPT, (field, i))])
                        if item is not None:
                            new_values.append(item)
                            continue
                        elif not isinstance(item, ast.AST):
                            new_values.extend(item)
                            continue
                    new_values.append(item)
                value[:] = new_values
            elif isinstance(value, ast.AST):
                new_node = self.visit(value, path + [(VisitType.ATTRIBUTE, field)])
                if new_node is None:
                    delattr(node, field)
                else:
                    setattr(node, field, new_node)
        return node

                        
