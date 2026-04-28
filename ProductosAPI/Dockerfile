# Etapa de construcción (Instala librerías y compila)
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY ["ProductosAPI.csproj", "./"]
RUN dotnet restore "ProductosAPI.csproj"
COPY . .
RUN dotnet publish "ProductosAPI.csproj" -c Release -o /app/publish

# Etapa de ejecución (Contenedor final ligero)
FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/publish .
# Comando para iniciar la aplicación compilada
ENTRYPOINT ["dotnet", "ProductosAPI.dll"]