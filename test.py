def greet(name="world"):
    print(f"Hello, {name}!")

if __name__ == "__main__":
    greet()          # Uses default value
    greet("Alice")   # Uses provided argument