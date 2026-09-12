def set_colors(embeds: list[dict], color: int | None):
    """
    Sets the colors of the embeds.
    :param embeds: embeds
    :param color: color to set
    """
    if color is None:
        return

    for embed in embeds:
        embed['color'] = color


def set_color(embed: dict, color: int | None):
    """
    Sets the color of the embed.

    :param embed: embed
    :param color: color to set
    """
    if color is None:
        return

    embed['color'] = color
