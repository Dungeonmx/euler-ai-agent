/*
  Copiar al portapapeles.

  `navigator.clipboard` solo existe en contextos seguros (https, o localhost).
  El widget se incrusta en sitios que no siempre son https, asi que hace falta
  un camino de respaldo con `document.execCommand("copy")`, que sigue
  funcionando en todos los navegadores aunque este deprecado.

  Devuelve si se pudo copiar, para poder avisarle al usuario (o no) en vez de
  fingir que salio bien.
*/
export const copyText = async (text) => {
  const valor = String(text ?? "");
  if (!valor) return false;

  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(valor);
      return true;
    }
  } catch (error) {
    // Sin permiso, sin contexto seguro, o el navegador enojado: se prueba el
    // camino de abajo.
  }

  try {
    const area = document.createElement("textarea");
    area.value = valor;
    area.setAttribute("readonly", "");
    // Fuera de la vista, pero seleccionable: el `execCommand` necesita que el
    // elemento este en el documento.
    area.style.cssText =
      "position:fixed;top:0;left:0;width:1px;height:1px;padding:0;border:0;opacity:0;pointer-events:none;";
    document.body.appendChild(area);
    area.select();
    area.setSelectionRange(0, area.value.length);

    const ok = document.execCommand("copy");
    document.body.removeChild(area);
    return ok;
  } catch (error) {
    return false;
  }
};
