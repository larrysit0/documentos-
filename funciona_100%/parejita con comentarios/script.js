// ============================================================================
// SISTEMA DE ALERTA VECINAL - JAVASCRIPT DEL CLIENTE
// ============================================================================
// Este script maneja toda la interacción del usuario en la página web
// del botón de emergencia. Se ejecuta cuando el usuario abre el WebApp
// desde Telegram después de presionar el botón "ABRIR BOTÓN DE EMERGENCIA"
// ============================================================================

// 🚀 Event listener que se ejecuta cuando el DOM está completamente cargado
// Es crucial esperar a que todos los elementos HTML estén disponibles
document.addEventListener('DOMContentLoaded', () => {
  
  // ========================================================================
  // PASO 1: EXTRACCIÓN DE PARÁMETROS DE LA URL
  // ========================================================================
  // La URL llega con formato: https://servidor.com/?comunidad=villa&user_id=1667177404
  // Necesitamos extraer estos parámetros para identificar al usuario
  
  const urlParams = new URLSearchParams(window.location.search);
  const comunidadSeleccionada = urlParams.get('comunidad');  // ej: "villa"
  const telegramUserId = urlParams.get('user_id');           // ej: "1667177404" 🎯 CLAVE

  // Validación crítica: Sin comunidad no podemos hacer nada
  if (!comunidadSeleccionada) {
    alert("❌ No se especificó la comunidad en la URL.");
    return; // Termina la ejecución del script
  }

  // ========================================================================
  // PASO 2: INICIALIZACIÓN DE VARIABLES GLOBALES
  // ========================================================================
  // Estas variables almacenan el estado de la aplicación
  
  let ubicacionesPredeterminadas = [];  // Array con todos los miembros de la comunidad
  let ubicacionSeleccionada = null;     // Objeto del miembro específico que usaremos

  // ========================================================================
  // PASO 3: REFERENCIAS A ELEMENTOS HTML
  // ========================================================================
  // Obtenemos referencias a todos los elementos que vamos a manipular
  
  const textarea = document.getElementById('descripcion');      // Campo de texto para la descripción
  const boton = document.getElementById('btnEmergencia');       // Botón principal "Enviar Alerta Roja"
  const statusMsg = document.getElementById('statusMsg');       // Mensaje de estado en la parte inferior
  const toggleRealTime = document.getElementById('toggleRealTime'); // Switch para ubicación en tiempo real

  // ========================================================================
  // PASO 4: ACTUALIZACIÓN DE INTERFAZ INICIAL
  // ========================================================================
  // Muestra información relevante al usuario sobre su estado actual
  
  if (telegramUserId) {
    // Si tenemos el user_id, mostramos información detallada
    statusMsg.textContent = `👥 Comunidad: ${comunidadSeleccionada.toUpperCase()} | Usuario ID: ${telegramUserId}`;
    console.log(`🎯 Usuario identificado: ID ${telegramUserId} en comunidad ${comunidadSeleccionada}`);
  } else {
    // Si no tenemos user_id, solo mostramos la comunidad
    statusMsg.textContent = `👥 Comunidad detectada: ${comunidadSeleccionada.toUpperCase()}`;
    console.log(`⚠️ No se recibió user_id, usando modo fallback para comunidad ${comunidadSeleccionada}`);
  }
  
  // ========================================================================
  // PASO 5: CARGA INICIAL DE DATOS DE LA COMUNIDAD
  // ========================================================================
  // Inicia el proceso de carga de información de miembros de la comunidad
  
  cargarUbicaciones(comunidadSeleccionada);

  // ========================================================================
  // FUNCIÓN: CARGA DE UBICACIONES Y MIEMBROS
  // ========================================================================
  
  function cargarUbicaciones(comunidad) {
    /**
     * 📍 FUNCIÓN CRUCIAL PARA IDENTIFICACIÓN DEL USUARIO
     * 
     * Esta función:
     * 1. Descarga la lista de todos los miembros de la comunidad
     * 2. Identifica al usuario específico que abrió la aplicación
     * 3. Configura los datos de ubicación predeterminados
     * 
     * @param {string} comunidad - Nombre de la comunidad (ej: "villa")
     */
    
    console.log(`📡 Cargando datos de la comunidad: ${comunidad}`);
    
    // Realiza petición al servidor para obtener miembros de la comunidad
    fetch(`/api/ubicaciones/${comunidad}`)
      .then(res => {
        if (!res.ok) throw new Error(`Error al cargar ubicaciones: ${res.status}`);
        return res.json();
      })
      .then(data => {
        // ================================================================
        // PROCESAMIENTO DE DATOS RECIBIDOS
        // ================================================================
        
        ubicacionesPredeterminadas = data; // Guarda todos los miembros
        console.log(`📦 Datos cargados: ${data.length} miembros encontrados`);
        
        // ================================================================
        // IDENTIFICACIÓN DEL USUARIO ESPECÍFICO (PARTE CRÍTICA)
        // ================================================================
        // Aquí resolvemos quién es exactamente el usuario que abrió la app
        
        if (telegramUserId) {
          // 🎯 MÉTODO PRINCIPAL: Buscar por telegram_id
          console.log(`🔍 Buscando miembro con telegram_id: ${telegramUserId}`);
          
          const usuarioEspecifico = data.find(miembro => 
            String(miembro.telegram_id) === String(telegramUserId)
          );
          
          if (usuarioEspecifico) {
            // ✅ USUARIO ENCONTRADO - Este es el escenario ideal
            ubicacionSeleccionada = usuarioEspecifico;
            statusMsg.textContent = `📍 Usuario: ${usuarioEspecifico.nombre} - ${usuarioEspecifico.direccion}`;
            console.log(`✅ Usuario identificado correctamente: ${usuarioEspecifico.nombre}`);
            console.log(`📍 Dirección: ${usuarioEspecifico.direccion}`);
            console.log(`🗺️ Coordenadas: ${usuarioEspecifico.geolocalizacion?.lat}, ${usuarioEspecifico.geolocalizacion?.lon}`);
          } else {
            // ⚠️ USUARIO NO ENCONTRADO EN JSON
            console.warn(`⚠️ Usuario con ID ${telegramUserId} no encontrado en el JSON de la comunidad`);
            console.warn('🔧 Esto puede suceder si:');
            console.warn('   - El usuario no está registrado en el JSON');
            console.warn('   - El telegram_id en el JSON es incorrecto');
            console.warn('   - Hay un problema de sincronización');
            
            // Fallback: usar el primer miembro disponible
            ubicacionSeleccionada = ubicacionesPredeterminadas[0];
            if (ubicacionSeleccionada) {
              statusMsg.textContent = `📍 Usando ubicación predeterminada de ${ubicacionSeleccionada.nombre}`;
              console.log(`🔄 Usando fallback: ${ubicacionSeleccionada.nombre}`);
            }
          }
        } else {
          // 🔄 MODO FALLBACK: Sin user_id, usar primer miembro
          console.log('🔄 Modo fallback activado: no hay telegram_user_id disponible');
          ubicacionSeleccionada = ubicacionesPredeterminadas[0];
          if (ubicacionSeleccionada) {
            statusMsg.textContent = `📍 Usando ubicación predeterminada de ${ubicacionSeleccionada.nombre}`;
            console.log(`📍 Usando primer miembro: ${ubicacionSeleccionada.nombre}`);
          }
        }
        
        // Validación final
        if (!ubicacionSeleccionada) {
          console.error('❌ No se pudo seleccionar ningún miembro');
          statusMsg.textContent = "❌ Error: No hay miembros disponibles";
        }
      })
      .catch(error => {
        // Manejo de errores de red o servidor
        console.error("❌ Error cargando ubicaciones:", error.message);
        statusMsg.textContent = "❌ No se pudieron cargar las ubicaciones.";
        
        // En caso de error, el botón quedará deshabilitado
        // y el usuario verá un mensaje de error claro
      });
  }

  // ========================================================================
  // EVENTO: MONITOREO DEL CAMPO DE DESCRIPCIÓN
  // ========================================================================
  
  textarea.addEventListener('input', () => {
    /**
     * 📝 VALIDACIÓN EN TIEMPO REAL DEL TEXTO
     * 
     * Se ejecuta cada vez que el usuario escribe o borra en el textarea
     * Habilita/deshabilita el botón según las reglas de validación
     */
    
    const texto = textarea.value.trim(); // Remueve espacios al inicio y final
    
    // Reglas de validación:
    // - Mínimo 4 caracteres (evita envíos accidentales)
    // - Máximo 300 caracteres (límite definido en el HTML)
    if (texto.length >= 4 && texto.length <= 300) {
      // ✅ TEXTO VÁLIDO - Habilitar botón
      boton.disabled = false;
      boton.classList.add('enabled'); // Clase CSS para efecto visual
      
      // Actualizar mensaje de estado con información del usuario
      if (ubicacionSeleccionada) {
        statusMsg.textContent = `✅ Listo para enviar (${ubicacionSeleccionada.nombre})`;
      } else {
        statusMsg.textContent = "✅ Listo para enviar";
      }
      
      console.log(`📝 Texto válido: ${texto.length} caracteres`);
    } else {
      // ❌ TEXTO INVÁLIDO - Deshabilitar botón
      boton.disabled = true;
      boton.classList.remove('enabled');
      
      if (texto.length < 4 && texto.length > 0) {
        statusMsg.textContent = `⏳ Mínimo 4 caracteres (actual: ${texto.length})`;
      } else if (texto.length > 300) {
        statusMsg.textContent = `⚠️ Máximo 300 caracteres (actual: ${texto.length})`;
      } else {
        statusMsg.textContent = "⏳ Esperando acción del usuario...";
      }
    }
  });

  // ========================================================================
  // EVENTO: TOGGLE DE UBICACIÓN EN TIEMPO REAL
  // ========================================================================
  
  toggleRealTime.addEventListener('change', () => {
    /**
     * 🗺️ MANEJO DEL SWITCH DE GEOLOCALIZACIÓN
     * 
     * Permite al usuario elegir entre:
     * - Ubicación en tiempo real (GPS del dispositivo)
     * - Ubicación predeterminada (del JSON de la comunidad)
     */
    
    if (toggleRealTime.checked) {
      // ✅ ACTIVADO: Usar GPS del dispositivo
      statusMsg.textContent = "📍 Usando ubicación en tiempo real";
      console.log('🛰️ Modo GPS activado');
      
      // Verificar si el navegador soporta geolocalización
      if (!navigator.geolocation) {
        console.warn('⚠️ Este navegador no soporta geolocalización');
        statusMsg.textContent = "⚠️ GPS no disponible en este dispositivo";
      }
    } else {
      // ❌ DESACTIVADO: Usar ubicación predeterminada
      if (ubicacionSeleccionada) {
        statusMsg.textContent = `📍 Usuario: ${ubicacionSeleccionada.nombre} - ${ubicacionSeleccionada.direccion}`;
        console.log(`🏠 Usando ubicación predeterminada de ${ubicacionSeleccionada.nombre}`);
      } else {
        statusMsg.textContent = "📍 Usando ubicación predeterminada";
      }
    }
  });

  // ========================================================================
  // EVENTO PRINCIPAL: ENVÍO DE ALERTA
  // ========================================================================
  
  boton.addEventListener('click', () => {
    /**
     * 🚨 FUNCIÓN MÁS IMPORTANTE DEL CLIENTE
     * 
     * Se ejecuta cuando el usuario presiona "Enviar Alerta Roja"
     * Coordina todo el proceso de envío de la emergencia
     */
    
    console.log('🚨 Iniciando proceso de envío de alerta...');
    
    // ================================================================
    // VALIDACIONES PREVIAS
    // ================================================================
    
    const descripcion = textarea.value.trim();

    // Validación de datos mínimos requeridos
    if (!descripcion || !comunidadSeleccionada || !ubicacionSeleccionada) {
      console.error('❌ Faltan datos necesarios:', {
        descripcion: !!descripcion,
        comunidad: !!comunidadSeleccionada,
        ubicacion: !!ubicacionSeleccionada
      });
      alert("❌ Faltan datos necesarios");
      return;
    }

    // ================================================================
    // PREPARACIÓN DE LA INTERFAZ
    // ================================================================
    
    // Deshabilitar botón para evitar envíos múltiples
    boton.disabled = true;
    boton.textContent = "Enviando...";  // Feedback visual inmediato
    statusMsg.textContent = "🔄 Enviando alerta...";
    
    console.log('📤 Preparando envío de alerta');
    console.log(`📝 Descripción: "${descripcion}"`);
    console.log(`🏘️ Comunidad: ${comunidadSeleccionada}`);
    console.log(`👤 Usuario: ${ubicacionSeleccionada.nombre}`);

    // ================================================================
    // MANEJO DE GEOLOCALIZACIÓN
    // ================================================================
    
    if (toggleRealTime.checked && navigator.geolocation) {
      // 🛰️ MODO GPS: Obtener ubicación actual del dispositivo
      console.log('🛰️ Solicitando ubicación GPS...');
      
      navigator.geolocation.getCurrentPosition(
        // ✅ Éxito: GPS obtenido correctamente
        (pos) => {
          const lat = pos.coords.latitude;
          const lon = pos.coords.longitude;
          console.log(`📍 GPS obtenido: ${lat}, ${lon}`);
          console.log(`📏 Precisión: ${pos.coords.accuracy} metros`);
          
          enviarAlerta(descripcion, lat, lon, true); // true = es ubicación GPS
        },
        // ❌ Error: No se pudo obtener GPS
        (error) => {
          console.error('❌ Error de geolocalización:', error.message);
          console.log('🔄 Códigos de error GPS:');
          console.log('  1 = Permiso denegado');
          console.log('  2 = Posición no disponible');
          console.log('  3 = Timeout');
          
          alert("❌ No se pudo obtener ubicación en tiempo real.");
          resetFormulario();
        },
        // ⚙️ Opciones de geolocalización
        {
          enableHighAccuracy: true, // Usar GPS de alta precisión
          timeout: 10000,          // Timeout de 10 segundos
          maximumAge: 60000        // Aceitar ubicaciones de hasta 1 minuto
        }
      );
    } else {
      // 🏠 MODO PREDETERMINADO: Usar coordenadas del JSON
      console.log('🏠 Usando ubicación predeterminada');
      
      // Validar que la ubicación tenga coordenadas
      if (!ubicacionSeleccionada.geolocalizacion) {
        console.error('❌ No hay geolocalización en el miembro seleccionado:', ubicacionSeleccionada);
        alert("❌ No se ha seleccionado una ubicación válida.");
        resetFormulario();
        return;
      }
      
      const { lat, lon } = ubicacionSeleccionada.geolocalizacion;
      console.log(`📍 Coordenadas predeterminadas: ${lat}, ${lon}`);
      
      enviarAlerta(descripcion, lat, lon, false); // false = no es GPS en tiempo real
    }
  });

  // ========================================================================
  // FUNCIÓN: ENVÍO DE ALERTA AL SERVIDOR
  // ========================================================================
  
  function enviarAlerta(descripcion, lat, lon, esUbicacionTiempoReal) {
    /**
     * 📡 COMUNICACIÓN CON EL SERVIDOR
     * 
     * Envía todos los datos de la emergencia al servidor Flask
     * Esta función es el puente entre el frontend y el backend
     * 
     * @param {string} descripcion - Texto escrito por el usuario
     * @param {number} lat - Latitud (GPS o predeterminada)
     * @param {number} lon - Longitud (GPS o predeterminada)
     * @param {boolean} esUbicacionTiempoReal - True si es GPS, false si es predeterminada
     */
    
    console.log('📡 Preparando petición al servidor...');
    
    // ================================================================
    // CONSTRUCCIÓN DEL PAYLOAD
    // ================================================================
    
    const direccion = ubicacionSeleccionada.direccion || "Dirección no disponible";
    
    // 📦 Construcción del objeto JSON que se enviará al servidor
    const payload = {
      tipo: "Alerta Roja Activada",                    // Tipo fijo de alerta
      descripcion: descripcion,                        // Texto del usuario
      ubicacion: { lat: lat, lon: lon },              // Coordenadas (GPS o predeterminadas)
      direccion: direccion,                            // Dirección del miembro
      comunidad: comunidadSeleccionada,                // Nombre de la comunidad
      ubicacion_tiempo_real: esUbicacionTiempoReal     // Flag para el servidor
    };

    // 🎯 PARTE CRUCIAL: Agregar telegram_user_id si está disponible
    // Esto permite al servidor identificar exactamente quién envió la alerta
    if (telegramUserId) {
      payload.telegram_user_id = telegramUserId;
      console.log(`🎯 Incluyendo telegram_user_id: ${telegramUserId}`);
    } else {
      console.log('⚠️ No hay telegram_user_id disponible, el servidor usará fallback');
    }

    // Log completo del payload para debugging
    console.log("📦 Payload completo:", JSON.stringify(payload, null, 2));

    // ================================================================
    // PETICIÓN HTTP AL SERVIDOR
    // ================================================================
    
    fetch('/api/alert', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json'  // Importante: especificar tipo JSON
      },
      body: JSON.stringify(payload)  // Convertir objeto a JSON string
    })
      .then(res => {
        console.log(`📡 Respuesta del servidor: ${res.status} ${res.statusText}`);
        return res.json();
      })
      .then(data => {
        // ✅ ÉXITO: Alerta enviada correctamente
        console.log('✅ Respuesta del servidor:', data);
        
        // Mostrar mensaje de confirmación al usuario
        const mensajeExito = data.status || "✅ Alerta enviada correctamente.";
        alert(mensajeExito);
        
        // Resetear el formulario para permitir nuevas alertas
        resetFormulario();
        
        // ================================================================
        // INTEGRACIÓN CON TELEGRAM WEB APP
        // ================================================================
        
        // Si estamos dentro de Telegram WebApp, cerrar automáticamente
        if (window.Telegram && window.Telegram.WebApp) {
          console.log('📱 Cerrando Telegram WebApp en 2 segundos...');
          setTimeout(() => {
            window.Telegram.WebApp.close();
          }, 2000);
        }
      })
      .catch(err => {
        // ❌ ERROR: Algo salió mal en la comunicación
        console.error("❌ Error al enviar alerta:", err);
        
        // Log de debugging detallado
        console.log('🔍 Información de debug:');
        console.log('  - URL del servidor:', window.location.origin);
        console.log('  - Payload enviado:', payload);
        console.log('  - Error completo:', err);
        
        alert("❌ Error al enviar alerta. Revisa tu conexión e intenta nuevamente.");
        resetFormulario();
      });
  }

  // ========================================================================
  // FUNCIÓN: RESET DEL FORMULARIO
  // ========================================================================
  
  function resetFormulario() {
    /**
     * 🔄 RESTAURAR ESTADO INICIAL
     * 
     * Vuelve el formulario a su estado original para permitir
     * nuevas alertas o reintentos en caso de error
     */
    
    console.log('🔄 Reseteando formulario...');
    
    // Rehabilitar y restaurar botón
    boton.disabled = true;  // Queda deshabilitado hasta que se escriba texto válido
    boton.textContent = "🚨 Enviar Alerta Roja";  // Texto original
    boton.classList.remove('enabled');  // Remover estilo de habilitado
    
    // Limpiar campo de texto
    textarea.value = "";
    
    // Restaurar mensaje de estado
    statusMsg.textContent = "⏳ Esperando acción del usuario...";
    
    console.log('✅ Formulario reseteado correctamente');
  }

  // ========================================================================
  // INTEGRACIÓN CON TELEGRAM WEB APP
  // ========================================================================
  
  // Configuración especial si estamos ejecutando dentro de Telegram
  if (window.Telegram && window.Telegram.WebApp) {
    console.log('📱 Telegram WebApp detectado');
    
    // Notificar a Telegram que la app está lista
    window.Telegram.WebApp.ready();
    
    // Expandir la WebApp a pantalla completa
    window.Telegram.WebApp.expand();
    
    // Log de información de Telegram para debugging
    console.log('📱 Info de Telegram WebApp:', {
      initData: window.Telegram.WebApp.initData,
      version: window.Telegram.WebApp.version,
      platform: window.Telegram.WebApp.platform,
      colorScheme: window.Telegram.WebApp.colorScheme
    });
  } else {
    console.log('🌐 Ejecutando en navegador normal (no Telegram WebApp)');
  }
});

// ============================================================================
// FLUJO COMPLETO DEL JAVASCRIPT:
// ============================================================================
//
// 1. INICIALIZACIÓN:
//    - Se extrae comunidad y user_id de la URL
//    - Se obtienen referencias a elementos HTML
//    - Se muestra información inicial al usuario
//
// 2. CARGA DE DATOS:
//    - Se descarga el JSON de la comunidad desde /api/ubicaciones/{comunidad}
//    - Se identifica al usuario específico por su telegram_id
//    - Se configura su información como ubicación seleccionada
//
// 3. INTERACCIÓN DEL USUARIO:
//    - Se monitora el texto escrito en el textarea
//    - Se habilita/deshabilita el botón según validaciones
//    - Se permite cambiar entre GPS y ubicación predeterminada
//
// 4. ENVÍO DE ALERTA:
//    - Se validan todos los datos necesarios
//    - Se obtiene ubicación (GPS o predeterminada)
//    - Se construye payload completo con toda la información
//    - Se envía POST a /api/alert
//
// 5. RESPUESTA:
//    - Se muestra confirmación al usuario
//    - Se resetea el formulario
//    - Se cierra la WebApp si estamos en Telegram
//
// ============================================================================
//
// VARIABLES CLAVE PARA EL FUNCIONAMIENTO:
// - telegramUserId: ID único del usuario que abrió la app
// - ubicacionSeleccionada: Objeto del miembro identificado en el JSON
// - comunidadSeleccionada: Nombre de la comunidad desde la URL
//
// FLUJO DE IDENTIFICACIÓN DE USUARIO:
// URL → user_id → JSON.find(telegram_id) → ubicacionSeleccionada
//
// ============================================================================
