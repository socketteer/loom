
def move_object(canvas, object_id, destination, speed=50):
    dest_x, dest_y = destination
    coords = canvas.coords(object_id)
    current_x = coords[0]
    current_y = coords[1]

    new_x, new_y = current_x, current_y
    delta_x = delta_y = 0
    if current_x < dest_x:
        delta_x = 1
    elif current_x > dest_x:
        delta_x = -1

    if current_y < dest_y:
        delta_y = 1
    elif current_y > dest_y:
        delta_y = -1

    if (delta_x, delta_y) != (0, 0):
        canvas.move(object_id, delta_x, delta_y)

    if (new_x, new_y) != (dest_x, dest_y):
        canvas.after(speed, move_object, canvas, object_id, destination, speed)

