apple-minimalist-ui-ux
Disena y desarrolla interfaces de usuario (UI) y experiencias de usuario (UX) minimalistas, premium y con estetica inspirada en Apple. Usala cuando el usuario pida crear, disenar, estilizar o mejorar una UI, pagina web, app, componente, dashboard, landing page o flujo UX buscando un acabado limpio, elegante, moderno o estilo Apple.

Instructions
Apple Minimalist UI UX
Disena y construye interfaces minimalistas de alta gama y experiencias de usuario fluidas, basadas en tres pilares: claridad tipografica, deferencia al contenido y profundidad sutil.

Cuando usar esta skill
Al crear componentes, pantallas, dashboards o landing pages en HTML, CSS, Tailwind, React u otro framework.
Al redisenar una interfaz existente para darle un aspecto mas limpio, moderno y premium.
Al definir tokens de diseno, paletas de colores o flujos de interaccion centrados en la simplicidad.
Flujo de trabajo
Definir la jerarquia primero: Identifica la accion principal de la pantalla y elimina cualquier elemento que compita con ella.
Aplicar tokens de color estilo Apple: Usa superficies neutras suaves y reserva el color de acento exclusivamente para acciones primarias y estados interactivos.
Construir la tipografia y el ritmo espacial: Establece contrastes claros de tamano y peso, dejando espacio en blanco generoso para que el contenido respire.
Anadir profundidad sutil y micro-interacciones: Incorpora translucidez controlada, sombras difusas y transiciones suaves que den feedback inmediato.
Validar UX y accesibilidad: Verifica contraste de texto, estados de carga, estados vacios y navegacion por teclado antes de entregar el codigo.
Sistema de diseno (UI)
Paleta de colores
Usa una paleta neutra refinada en lugar de blancos o negros duros sin matices.

Modo Claro: Fondo base #F5F5F7, superficie elevada #FFFFFF, texto primario #1D1D1F, texto secundario #6E6E73, borde sutil rgba(0, 0, 0, 0.08), acento primario #0071E3 (hover #0077ED).
Modo Oscuro: Fondo base #000000, superficie elevada #1C1C1E, superficie secundaria #2C2C2E, texto primario #F5F5F7, texto secundario #86868B, borde sutil rgba(255, 255, 255, 0.12), acento primario #0A84FF.
Colores semanticos: Exito #34C759, advertencia #FF9500, error #FF3B30. Usalos con fondos tintados al 10%-15% de opacidad para badges o alertas.
Tipografia
Familia: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Inter", sans-serif.
Titulos: Peso semibold o bold (600-700), letter-spacing ligeramente negativo (-0.02em a -0.03em) y line-height compacto (1.1-1.2).
Cuerpo: Peso regular (400), tamano base 15px-17px, line-height de 1.5 para lectura comoda.
Numeros y metricas: Usa font-variant-numeric: tabular-nums para evitar saltos visuales en contadores o tablas.
Superficies, radios y profundidad
Radios de borde: Usa esquinas redondeadas consistentes (12px para botones e inputs, 18px-24px para tarjetas y modales, 9999px para pills y badges).
Glassmorphism sutil: Para barras de navegacion o paneles flotantes, aplica background: rgba(255, 255, 255, 0.72) (o rgba(28, 28, 30, 0.72) en modo oscuro) junto con backdrop-filter: blur(20px) saturate(180%).
Sombras: Prefiere sombras amplias y muy suaves (por ejemplo, 0 4px 24px rgba(0, 0, 0, 0.06)) en lugar de sombras oscuras o recortadas.
Principios de experiencia de usuario (UX)
Divulgacion progresiva: Muestra solo lo esencial en el primer nivel; oculta opciones avanzadas detras de menus limpios, drawers o acordeones.
Movimiento con fisica natural: Usa transiciones de 200ms-300ms con curvas suaves como cubic-bezier(0.25, 0.1, 0.25, 1). Anima solo transform y opacity para mantener 60fps.
Feedback tactil visual: Aplica escalados sutiles al presionar botones (active:scale-[0.98]), estados de focus claros con anillos suaves (ring-2 ring-[#0071E3]/40) y transiciones fluidas en hover.
Estados completos: Disena siempre el estado vacio (mensaje claro + accion sugerida), el estado de carga (skeletons suaves en vez de spinners agresivos) y mensajes de error humanos y accionables.
Accesibilidad: Respeta prefers-reduced-motion, mantiene contraste minimo WCAG AA (4.5:1 para texto normal) y asegura areas clicables de al menos 44x44px en dispositivos tactiles.
Errores comunes a evitar
Exceso de color: Evita usar mas de un color de acento principal por pantalla; el lujo visual viene de los neutros y el espacio.
Bordes y divisores pesados: Reemplaza lineas divisorias oscuras por espaciado generoso o diferencias sutiles de fondo entre capas.
Minimalismo que oculta la funcionalidad: Nunca elimines etiquetas, iconos claros o estados de hover/focus si eso hace que el usuario dude de que es interactivo.
Animaciones lentas o distractivas: Si una animacion retrasa al usuario o supera los 400ms en interacciones cotidianas, reducela.