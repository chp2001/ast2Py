# ast2Py

Wrapper module for built-in python library ast.
Adds additional functionality to the NodeVisitor and NodeTransformer classes:
By including a path argument in all of their methods, the user can use the value of that argument to programmatically reconstruct the syntax tree.

## Use Case

The main use case for this module is to allow the user to programmatically take actions on ast nodes based on their locations in the syntax tree, rather than the default behavior of one-size-fits-all actions.
For example, the user may want to get a list of all global variables within a file, and they can achieve that by ensuring that there is only an Assignment node between the root node and the node they are currently visiting.
