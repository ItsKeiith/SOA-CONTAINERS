using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Microsoft.OpenApi.Models;

var builder = WebApplication.CreateBuilder(args);
builder.WebHost.UseUrls("http://0.0.0.0:8002");

// Configurar la seguridad JWT
var secretKey = "secret_password_login_super_segura_32";
var key = Encoding.UTF8.GetBytes(secretKey);

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuerSigningKey = true,
            IssuerSigningKey = new SymmetricSecurityKey(key),
            ValidateIssuer = false,   
            ValidateAudience = false, 
            ValidateLifetime = true,
            ClockSkew = TimeSpan.Zero
        };
    });
builder.Services.AddAuthorization();
builder.Services.AddHttpClient(); 

// ACTIVAR SWAGGER Y CONFIGURAR EL CANDADO JWT
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new OpenApiInfo { Title = "Microservicio de Productos", Version = "v1" });
    
    // Configurar el botón "Authorize" para pegar el Token
    c.AddSecurityDefinition("Bearer", new OpenApiSecurityScheme
    {
        Name = "Authorization",
        Type = SecuritySchemeType.Http,
        Scheme = "Bearer",
        BearerFormat = "JWT",
        In = ParameterLocation.Header,
        Description = "Token generado en el microservicio de clientes aqui"
    });

    c.AddSecurityRequirement(new OpenApiSecurityRequirement
    {
        {
            new OpenApiSecurityScheme
            {
                Reference = new OpenApiReference { Type = ReferenceType.SecurityScheme, Id = "Bearer" }
            },
            Array.Empty<string>()
        }
    });
});

// Construir la aplicación
var app = builder.Build();

// Mostrar interfaz Swagger
app.UseSwagger();
app.UseSwaggerUI();

// FUNCIONES PARA .TXT
string filePath = "productos.txt";

List<Producto> CargarProductos()
{
    var lista = new List<Producto>();
    if (!File.Exists(filePath)) return lista;

    var lineas = File.ReadAllLines(filePath).Skip(1); 
    foreach (var linea in lineas)
    {
        var datos = linea.Split('|');
        if (datos.Length == 2)
        {
            lista.Add(new Producto { Id_producto = int.Parse(datos[0]), Descripcion = datos[1] });
        }
    }
    return lista;
}

void GuardarProductos(List<Producto> productos)
{
    using var writer = new StreamWriter(filePath, false, Encoding.UTF8);
    writer.WriteLine("id_producto|descripcion");
    foreach (var p in productos)
    {
        writer.WriteLine($"{p.Id_producto}|{p.Descripcion}");
    }
}

var db_productos = CargarProductos();

// ENDPOINTS PROTEGIDOS
app.UseAuthentication();
app.UseAuthorization();

app.MapGet("/productos", () =>
{
    return Results.Ok(db_productos);
}).RequireAuthorization(); 


app.MapPost("/productos", (Producto nuevo_producto) =>
{
    if (db_productos.Any(p => p.Id_producto == nuevo_producto.Id_producto))
    {
        return Results.BadRequest(new { detail = "Error (PK): El producto ya existe en el catálogo." });
    }

    db_productos.Add(nuevo_producto);
    GuardarProductos(db_productos);
    return Results.Ok(new { mensaje = "Producto registrado y guardado" });
}).RequireAuthorization();


app.MapPatch("/productos/{id_producto}", (int id_producto, ProductoUpdate datos_nuevos) =>
{
    var producto_actual = db_productos.FirstOrDefault(p => p.Id_producto == id_producto);
    if (producto_actual == null)
    {
        return Results.NotFound(new { detail = $"No se encontró el producto con ID {id_producto}" });
    }

    if (!string.IsNullOrEmpty(datos_nuevos.Descripcion))
    {
        producto_actual.Descripcion = datos_nuevos.Descripcion;
    }

    GuardarProductos(db_productos);
    return Results.Ok(new { mensaje = "Producto actualizado correctamente", datos = producto_actual });
}).RequireAuthorization();


app.MapDelete("/productos/{id_producto}", async (int id_producto, IHttpClientFactory httpClientFactory, HttpContext context) =>
{
    var producto_a_borrar = db_productos.FirstOrDefault(p => p.Id_producto == id_producto);
    if (producto_a_borrar == null)
    {
        return Results.NotFound(new { detail = $"No se encontró el producto con ID {id_producto}" });
    }

    var token = context.Request.Headers["Authorization"].ToString().Replace("Bearer ", "");
    
    var client = httpClientFactory.CreateClient();
    client.DefaultRequestHeaders.Add("Authorization", $"Bearer {token}");
    
    try
    {
        var response = await client.GetAsync("http://inventario:8003/inventario/v1"); 
        if (response.IsSuccessStatusCode)
        {
            var inventarioJson = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(inventarioJson);
            
            foreach (var item in doc.RootElement.EnumerateArray())
            {
                if (item.GetProperty("id_producto").GetInt32() == id_producto)
                {
                    return Results.BadRequest(new { detail = "Error de Integridad: No puedes borrar este producto porque tiene stock asignado en el Inventario. Borra su stock primero." });
                }
            }
        }
    }
    catch (HttpRequestException)
    {
        return Results.StatusCode(503); 
    }

    db_productos.Remove(producto_a_borrar);
    GuardarProductos(db_productos);
    return Results.Ok(new { mensaje = $"Producto {id_producto} eliminado exitosamente y de forma segura" });
}).RequireAuthorization();

app.Run();

// MODELOS DE DATOS
class Producto
{
    public int Id_producto { get; set; }
    public string Descripcion { get; set; } = "";
}

class ProductoUpdate
{
    public string? Descripcion { get; set; }
}