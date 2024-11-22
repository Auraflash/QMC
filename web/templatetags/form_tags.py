from django import template

register = template.Library()

@register.filter(name='addclass')
def addclass(field, css):
    if hasattr(field, 'as_widget'):
        return field.as_widget(attrs={"class": css})
    else:
        return field.replace('class="', f'class="{css} ') 